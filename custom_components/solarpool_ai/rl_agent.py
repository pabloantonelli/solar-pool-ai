"""Reinforcement Learning Agent for SolarPool AI.

This module implements a Q-Learning agent that learns optimal pump control
strategies based on thermal efficiency feedback.
"""
from __future__ import annotations

import logging
import json
import random
from typing import Any

import numpy as np

from .const import (
    RL_ACTIONS,
    DEFAULT_RL_WARMUP_EPISODES,
    DEFAULT_RL_EXPLORATION_RATE,
    DEFAULT_RL_MIN_EXPLORATION,
)

_LOGGER = logging.getLogger(__name__)


class RLAgent:
    """Q-Learning agent for solar pool pump control.
    
    State space: (delta_bin, uv_bin, wind_bin, elevation_bin)
    - delta_bin: 4 levels (0-2, 2-4, 4-6, 6+)
    - uv_bin: 4 levels (0-3, 3-6, 6-9, 9+)
    - wind_bin: 3 levels (0-15, 15-30, 30+)
    - elevation_bin: 3 niveles (0-20, 20-45, 45+)
    
    Total de estados: 4 × 4 × 3 × 3 = 144 estados posibles
    
    Acciones: [APAGADO, ON_20min, ON_40min, ON_60min, ON_90min]
    """
    
    # Búferes para la discretización de estados (conversión de valores continuos a categorías)
    DELTA_BINS = [0, 2, 4, 6, float('inf')]
    UV_BINS = [0, 3, 6, 9, float('inf')]
    WIND_BINS = [0, 15, 30, float('inf')]
    ELEVATION_BINS = [0, 20, 45, float('inf')]
    
    # Hiperparámetros de Q-Learning
    ALPHA = 0.1  # Tasa de aprendizaje (qué tanto valoramos la nueva información)
    GAMMA = 0.9  # Factor de descuento (valor de recompensas futuras)
    
    def __init__(
        self,
        q_table: list[list[float]] | None = None,
        episode_count: int = 0,
    ) -> None:
        """Initialize the RL agent.
        
        Args:
            q_table: Pre-trained Q-table (optional)
            episode_count: Number of episodes already completed
        """
        self.num_states = 4 * 4 * 3 * 3  # 144 states
        self.num_actions = len(RL_ACTIONS)  # 5 actions
        
        # Initialize Q-table
        if q_table is not None and len(q_table) == self.num_states:
            self.q_table = np.array(q_table)
        else:
            if q_table is not None:
                _LOGGER.warning("RL Agent: Q-table size mismatch (expected %d, got %d). Resetting.", 
                              self.num_states, len(q_table))
            # Initialize with small random values to break ties
            self.q_table = np.random.uniform(0, 0.01, (self.num_states, self.num_actions))
        
        self.episode_count = episode_count
        self.last_state: int | None = None
        self.last_action: int | None = None
        
    @property
    def is_warmup(self) -> bool:
        """Check if agent is still in warmup phase."""
        return self.episode_count < DEFAULT_RL_WARMUP_EPISODES
    
    @property
    def exploration_rate(self) -> float:
        """Calculate current exploration rate (epsilon)."""
        if self.episode_count < 10:
            return 1.0  # 100% exploration in first 10 episodes
        elif self.episode_count < DEFAULT_RL_WARMUP_EPISODES:
            # Linear decay from initial to minimum
            progress = (self.episode_count - 10) / (DEFAULT_RL_WARMUP_EPISODES - 10)
            return DEFAULT_RL_EXPLORATION_RATE * (1 - progress) + DEFAULT_RL_MIN_EXPLORATION * progress
        else:
            return DEFAULT_RL_MIN_EXPLORATION
    
    def discretize_state(self, context: dict[str, Any]) -> int:
        """Convierte los datos de los sensores en un índice de estado único (0-143).
        
        Este proceso es vital para que la IA pueda 'agrupar' situaciones similares.
        """
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        uv = context.get("uv_index", 0)
        elevation = context.get("sun_elevation", 0)
        wind = context.get("wind_speed", 0)
        
        # Discretize each dimension
        delta_bin = self._bin_value(delta, self.DELTA_BINS)
        uv_bin = self._bin_value(uv, self.UV_BINS)
        wind_bin = self._bin_value(wind, self.WIND_BINS)
        elevation_bin = self._bin_value(elevation, self.ELEVATION_BINS)
        
        # Convert to flat index
        # 4 (delta) * 4 (uv) * 3 (wind) * 3 (elevation)
        state = delta_bin * 36 + uv_bin * 9 + wind_bin * 3 + elevation_bin
        
        return min(state, self.num_states - 1)
    
    def _bin_value(self, value: float, bins: list[float]) -> int:
        """Bin a continuous value into discrete levels."""
        for i, threshold in enumerate(bins[1:]):
            if value < threshold:
                return i
        return len(bins) - 2
    
    def get_action(self, context: dict[str, Any]) -> dict[str, Any]:
        """Determina la mejor acción a tomar según el contexto actual.
        
        Utiliza una estrategia epsilon-greedy: la mayoría de las veces elige la mejor acción
        conocida, pero ocasionalmente 'explora' nuevas opciones para seguir aprendiendo.
        """
        state = self.discretize_state(context)
        self.last_state = state
        
        # Durante los primeros 10 ciclos (bootstrap), usamos reglas lógicas fijas
        if self.is_warmup and self.episode_count < 10:
            action, is_learning = self._get_warmup_action(context)
        else:
            # Selección de acción Epsilon-greedy
            if random.random() < self.exploration_rate:
                # EXPLORACIÓN: Elegimos una acción al azar
                action = random.randint(0, self.num_actions - 1)
                is_learning = True
                _LOGGER.debug("RL Agent: Explorando (ε=%.2f), acción=%d", self.exploration_rate, action)
            else:
                # EXPLOTACIÓN: Elegimos la acción con el valor Q más alto para este estado
                action = int(np.argmax(self.q_table[state]))
                is_learning = False
                _LOGGER.debug("RL Agent: Explotando conocimiento, estado=%d, acción=%d, Q=%.3f", 
                            state, action, self.q_table[state, action])
        
        self.last_action = action
        duration = RL_ACTIONS[action]
        
        # UV is already properly set by coordinator (sensor > weather > estimation)
        uv = context.get("uv_index", 0)
        
        return {
            "action": "OFF" if action == 0 else "ON",
            "heating_duration_minutes": duration,
            "expected_gain": self._estimate_gain(context, duration),
            "is_learning": is_learning,
            "is_warmup": self.is_warmup,
            "state_index": state,
            "q_values": self.q_table[state].tolist(),
        }
    
    def _get_warmup_action(self, context: dict[str, Any]) -> tuple[int, bool]:
        """Get action using deterministic rules during warmup.
        
        Conservative rules: only ON if delta > 4°C and UV > 5
        
        Returns:
            (action_index, is_learning)
        """
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        uv = context.get("uv_index", 0)
        wind = context.get("wind_speed", 0)
        
        # Conservative OFF conditions
        if delta < 4.0 or uv < 5:
            return 0, False  # OFF
        
        if wind > 25:
            return 0, False  # OFF
        
        # Determine duration based on conditions
        if delta > 6 and uv > 7 and wind < 15:
            return 4, False  # ON_90min
        elif delta > 5 and uv > 6:
            return 3, False  # ON_60min
        else:
            return 2, False  # ON_40min
    
    def _estimate_gain(self, context: dict[str, Any], duration: int) -> float:
        """Estimate thermal gain for a given duration.
        
        Args:
            context: Sensor context with uv_index, t_return, t_pool
            duration: Pump duration in minutes
            
        Returns:
            Estimated temperature gain in °C
        """
        if duration == 0:
            return 0.0
        
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        uv = context.get("uv_index", 0)
        
        # Efficiency factor: combines UV and delta influence
        # With UV=0 (cloudy), efficiency is very low
        efficiency_factor = max(0.05, min(1.0, uv / 10) * min(1.0, delta / 5))
        base_gain_per_hour = 1.0  # 1°C per hour under ideal conditions
        
        return round(max(0.0, efficiency_factor * base_gain_per_hour * (duration / 60)), 2)
    
    def update(self, reward: float, next_context: dict[str, Any] | None = None) -> None:
        """Actualiza la tabla Q basándose en la recompensa recibida tras la acción.
        
        Este es el núcleo del aprendizaje: ajusta los valores de la tabla Q para que
        las acciones que dieron buenos resultados sean más probables en el futuro.
        """
        if self.last_state is None or self.last_action is None:
            _LOGGER.warning("RL Agent: No se puede actualizar, falta estado/acción previa")
            return
        
        # Estimamos el valor máximo del siguiente estado (Bellman Equation)
        if next_context is not None:
            next_state = self.discretize_state(next_context)
            max_next_q = np.max(self.q_table[next_state])
        else:
            max_next_q = 0
        
        # Actualización de Q-Learning
        old_q = self.q_table[self.last_state, self.last_action]
        # Fórmula: NuevoQ = ViejoQ + ALPHA * (Recompensa + GAMMA * MaxSiguienteQ - ViejoQ)
        new_q = old_q + self.ALPHA * (reward + self.GAMMA * max_next_q - old_q)
        self.q_table[self.last_state, self.last_action] = new_q
        
        _LOGGER.info(
            "RL Update: estado=%d, acción=%d, recompensa=%.2f, Q: %.3f -> %.3f",
            self.last_state, self.last_action, reward, old_q, new_q
        )
        
        self.episode_count += 1
        self.last_state = None
        self.last_action = None
    
    def calculate_reward(
        self,
        actual_gain: float,
        duration_minutes: int,
        pump_cost_per_hour: float = 0.05, # Significant reduction in cost penalty
    ) -> float:
        """Calculate reward for a completed cycle.
        
        Args:
            actual_gain: Actual temperature increase (°C)
            duration_minutes: How long the pump was on
            pump_cost_per_hour: Cost penalty per hour of pump operation
            
        Returns:
            Reward value (positive = good decision, negative = bad decision)
        """
        if duration_minutes == 0:
            # OFF decision - small reward if correct (no potential gain wasted)
            return 0.1 if actual_gain < 0.5 else -0.5
        
        # ON decision - reward based on efficiency
        hours = duration_minutes / 60
        pump_cost = pump_cost_per_hour * hours
        
        # Reward = thermal benefit - cost
        reward = actual_gain - pump_cost
        
        # Bonus for efficient decisions
        if actual_gain > 1.0 and hours < 1.0:
            reward += 0.5  # Bonus for quick efficient heating
        
        return round(reward, 2)
    
    def to_dict(self) -> dict[str, Any]:
        """Export agent state for persistence."""
        return {
            "q_table": self.q_table.tolist(),
            "episode_count": self.episode_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RLAgent":
        """Create agent from persisted state."""
        return cls(
            q_table=data.get("q_table"),
            episode_count=data.get("episode_count", 0),
        )
