"""Agente de aprendizaje de SolarPool AI (v2).

Desde v0.1.0 el agente NO decide si calentar: eso lo resuelve el coordinator
midiendo el ΔT real con histéresis. El agente aprende una sola cosa:
**¿vale la pena hacer un barrido ahora?** (bandit contextual WAIT / SWEEP).

Un barrido cuesta energía de bomba; si las condiciones (UV, viento, elevación,
hora solar) casi nunca terminan en calentamiento, conviene esperar.

Atribución: `get_action` devuelve el estado y la acción; el coordinator los guarda
en la sesión y llama a `update(state, action, reward)` cuando la sesión termina.
No hay estado implícito "última acción" dentro del agente.
"""
from __future__ import annotations

import logging
import random
from typing import Any

from .const import (
    RL_ACTIONS,
    RL_ACTION_SWEEP,
    RL_ACTION_WAIT,
    DEFAULT_RL_BOOTSTRAP_EPISODES,
    DEFAULT_RL_WARMUP_EPISODES,
    DEFAULT_RL_EXPLORATION_RATE,
    DEFAULT_RL_MIN_EXPLORATION,
    RL_PUMP_COST_PER_HOUR,
    RL_SWEEP_COST,
)

_LOGGER = logging.getLogger(__name__)

AGENT_VERSION = 2


class RLAgent:
    """Bandit contextual para decidir cuándo barrer.

    Estado: (uv_bin, wind_bin, elevation_bin, solar_time_bin)
    - uv_bin: 4 niveles (0-3, 3-6, 6-9, 9+)   (UV efectivo, ya penalizado por nubes)
    - wind_bin: 3 niveles (0-15, 15-30, 30+ km/h)
    - elevation_bin: 3 niveles (0-20, 20-45, 45+ °)
    - solar_time_bin: 3 niveles (mañana < -1.5h, mediodía ±1.5h, tarde > +1.5h del mediodía solar)
    Total: 4 × 3 × 3 × 3 = 108 estados. Acciones: WAIT (0), SWEEP (1).

    Q[s, WAIT] queda en 0 (esperar no cuesta ni rinde); Q[s, SWEEP] es el promedio
    de recompensa de barrer en ese estado. Barrer conviene si Q[s, SWEEP] >= 0.
    """

    UV_BINS = [0, 3, 6, 9, float("inf")]
    WIND_BINS = [0, 15, 30, float("inf")]
    ELEVATION_BINS = [0, 20, 45, float("inf")]
    SOLAR_TIME_BINS = [float("-inf"), -1.5, 1.5, float("inf")]

    NUM_STATES = 4 * 3 * 3 * 3
    NUM_ACTIONS = len(RL_ACTIONS)

    MIN_ALPHA = 0.1  # tasa de aprendizaje mínima (promedio incremental hasta 1/n = 0.1)
    GAIN_RATE_ALPHA = 0.3  # suavizado del °C/h aprendido por estado
    INITIAL_SWEEP_Q = 0.01  # optimismo inicial: ante la duda, barrer

    def __init__(
        self,
        q_table: list[list[float]] | None = None,
        counts: list[int] | None = None,
        gain_rate: list[float | None] | None = None,
        episode_count: int = 0,
    ) -> None:
        """Inicializa el agente, descartando datos persistidos incompatibles."""
        if (
            q_table is not None
            and len(q_table) == self.NUM_STATES
            and all(len(row) == self.NUM_ACTIONS for row in q_table)
        ):
            self.q_table = [list(map(float, row)) for row in q_table]
            self.counts = list(counts) if counts and len(counts) == self.NUM_STATES else [0] * self.NUM_STATES
            self.gain_rate = (
                list(gain_rate) if gain_rate and len(gain_rate) == self.NUM_STATES else [None] * self.NUM_STATES
            )
            self.episode_count = episode_count
        else:
            if q_table is not None:
                _LOGGER.warning("RL Agent: tabla Q incompatible (formato anterior). Se reinicia el aprendizaje.")
            self.q_table = [[0.0, self.INITIAL_SWEEP_Q] for _ in range(self.NUM_STATES)]
            self.counts = [0] * self.NUM_STATES
            self.gain_rate = [None] * self.NUM_STATES
            self.episode_count = 0

    # ------------------------------------------------------------------ fases
    @property
    def is_bootstrap(self) -> bool:
        """Primeros episodios: siempre barrer (equivale al comportamiento clásico)."""
        return self.episode_count < DEFAULT_RL_BOOTSTRAP_EPISODES

    @property
    def is_warmup(self) -> bool:
        """Fase de entrenamiento (exploración decreciente)."""
        return self.episode_count < DEFAULT_RL_WARMUP_EPISODES

    @property
    def exploration_rate(self) -> float:
        """Epsilon actual."""
        if self.is_bootstrap:
            return 1.0
        if self.is_warmup:
            progress = (self.episode_count - DEFAULT_RL_BOOTSTRAP_EPISODES) / (
                DEFAULT_RL_WARMUP_EPISODES - DEFAULT_RL_BOOTSTRAP_EPISODES
            )
            return DEFAULT_RL_EXPLORATION_RATE * (1 - progress) + DEFAULT_RL_MIN_EXPLORATION * progress
        return DEFAULT_RL_MIN_EXPLORATION

    # ------------------------------------------------------------------ estado
    @staticmethod
    def _bin_value(value: float, bins: list[float]) -> int:
        """Ubica un valor continuo en su intervalo (bins incluye extremos)."""
        for i, threshold in enumerate(bins[1:]):
            if value < threshold:
                return i
        return len(bins) - 2

    def discretize_state(self, context: dict[str, Any]) -> int:
        """Convierte el contexto climático en un índice de estado (0-107)."""
        uv_bin = self._bin_value(float(context.get("uv_index") or 0), self.UV_BINS)
        wind_bin = self._bin_value(float(context.get("wind_speed") or 0), self.WIND_BINS)
        elev_bin = self._bin_value(float(context.get("sun_elevation") or 0), self.ELEVATION_BINS)
        time_bin = self._bin_value(float(context.get("solar_hour_offset") or 0), self.SOLAR_TIME_BINS)
        return ((uv_bin * 3 + wind_bin) * 3 + elev_bin) * 3 + time_bin

    # ---------------------------------------------------------------- decisión
    def get_action(self, context: dict[str, Any]) -> dict[str, Any]:
        """Decide si barrer ahora.

        Returns:
            dict con state, action (índice), action_name, is_learning, q_values.
        """
        state = self.discretize_state(context)
        q_wait, q_sweep = self.q_table[state]

        if self.is_bootstrap:
            action, is_learning = RL_ACTION_SWEEP, True
        elif q_sweep >= q_wait:
            action, is_learning = RL_ACTION_SWEEP, False
        elif random.random() < self.exploration_rate:
            # Solo tiene sentido explorar SWEEP: WAIT no genera información.
            action, is_learning = RL_ACTION_SWEEP, True
        else:
            action, is_learning = RL_ACTION_WAIT, False

        return {
            "state": state,
            "action": action,
            "action_name": RL_ACTIONS[action],
            "is_learning": is_learning,
            "q_values": [round(q_wait, 3), round(q_sweep, 3)],
        }

    def expected_gain(self, context: dict[str, Any], minutes: float = 60) -> float:
        """Ganancia esperada (°C) para `minutes` de calentamiento en el estado actual.

        Usa el °C/h aprendido de sesiones reales; si no hay datos, una heurística por UV.
        """
        state = self.discretize_state(context)
        rate = self.gain_rate[state]
        if rate is None:
            uv = float(context.get("uv_index") or 0)
            rate = max(0.05, min(1.0, uv / 10))  # ~1 °C/h en condiciones ideales
        return round(max(0.0, rate * minutes / 60), 2)

    # --------------------------------------------------------------- aprendizaje
    @staticmethod
    def calculate_reward(heated: bool, actual_gain: float, pump_minutes: float) -> float:
        """Recompensa de una sesión originada por un barrido.

        - Barrido que no calentó: -RL_SWEEP_COST (energía desperdiciada).
        - Barrido que calentó: ganancia real - costo de bomba.
        """
        if not heated:
            return -RL_SWEEP_COST
        return round(actual_gain - RL_PUMP_COST_PER_HOUR * pump_minutes / 60, 3)

    def update(self, state: int, action: int, reward: float) -> None:
        """Actualiza Q[state, action] con promedio incremental (atribución explícita)."""
        if not 0 <= state < self.NUM_STATES or not 0 <= action < self.NUM_ACTIONS:
            _LOGGER.warning("RL Agent: estado/acción inválidos (%s, %s)", state, action)
            return
        if action == RL_ACTION_WAIT:
            return  # WAIT no se aprende (Q fijo en 0)
        self.counts[state] += 1
        alpha = max(self.MIN_ALPHA, 1 / self.counts[state])
        old_q = self.q_table[state][action]
        new_q = old_q + alpha * (reward - old_q)
        self.q_table[state][action] = new_q
        self.episode_count += 1
        _LOGGER.info(
            "RL Update: estado=%d, acción=%s, recompensa=%.2f, Q: %.3f -> %.3f (episodio %d)",
            state, RL_ACTIONS[action], reward, old_q, new_q, self.episode_count,
        )

    def update_gain_rate(self, state: int, gain_per_hour: float) -> None:
        """Actualiza el °C/h observado para el estado (promedio móvil exponencial)."""
        if not 0 <= state < self.NUM_STATES:
            return
        old = self.gain_rate[state]
        self.gain_rate[state] = round(
            gain_per_hour if old is None else old + self.GAIN_RATE_ALPHA * (gain_per_hour - old), 3
        )

    # -------------------------------------------------------------- persistencia
    def to_dict(self) -> dict[str, Any]:
        """Exporta el estado para el Store."""
        return {
            "version": AGENT_VERSION,
            "q_table": self.q_table,
            "counts": self.counts,
            "gain_rate": self.gain_rate,
            "episode_count": self.episode_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RLAgent":
        """Crea el agente desde datos persistidos (o vacío)."""
        if not data or data.get("version") != AGENT_VERSION:
            return cls()
        return cls(
            q_table=data.get("q_table"),
            counts=data.get("counts"),
            gain_rate=data.get("gain_rate"),
            episode_count=data.get("episode_count", 0),
        )
