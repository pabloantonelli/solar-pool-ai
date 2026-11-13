"""Coordinator de SolarPool AI: máquina de estados que controla la bomba.

Resumen (ver CLAUDE.md para el detalle):
- Tick lento (cada `scan_interval` min): si es de día y no estamos usando la bomba,
  el agente RL decide si vale la pena barrer (WAIT / SWEEP).
- Barrido: prende la bomba hasta que el retorno se estabiliza y mide ΔT = retorno - pileta.
  ΔT >= delta_on → HEATING; si no, se apaga (respetando el tiempo mínimo de bomba).
- Tick rápido (60 s): monitorea HEATING por ΔT con histéresis (mediana de 3 lecturas,
  corta tras 3 lecturas < delta_off), protecciones (antiheladas, enfriamiento nocturno)
  y detección de problemas.
- La sesión (barrido + calentamiento) se cierra con una recompensa para el agente,
  atribuida explícitamente al (estado, acción) que la originó.
- Todo el estado persistente vive en un Store (.storage/solarpool_ai.<entry_id>).
"""
from __future__ import annotations

import logging
import math
import statistics
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_PUMP_STATES,
    COOLING_AMBIENT_GAP,
    COOLING_BLOCK_MINUTES,
    COOLING_MARGIN,
    CONF_AMBIENT_TEMP_SENSOR_ID,
    CONF_CLOUD_COVERAGE_SENSOR_ID,
    CONF_DELTA_OFF,
    CONF_DELTA_ON,
    CONF_FROST_PROTECTION,
    CONF_FROST_THRESHOLD,
    CONF_LANGUAGE,
    CONF_MAX_TEMP,
    CONF_NIGHT_COOLING,
    CONF_POOL_SENSOR_ID,
    CONF_PUMP_ENTITY_ID,
    CONF_RETURN_SENSOR_ID,
    CONF_SCAN_INTERVAL,
    CONF_SWEEP_DURATION,
    CONF_UV_SENSOR_ID,
    CONF_WEATHER_ENTITY_ID,
    CONF_WIND_SENSOR_ID,
    DEFAULT_DELTA_OFF,
    DEFAULT_DELTA_ON,
    DEFAULT_FROST_THRESHOLD,
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_RUN_TIME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SWEEP_DURATION,
    DELTA_MEDIAN_WINDOW,
    DELTA_OFF_CONSECUTIVE,
    DOMAIN,
    EVENT_PROBLEM,
    EVENT_SESSION_ENDED,
    FAST_TICK_SECONDS,
    FROST_CYCLE_MINUTES,
    FROST_HYSTERESIS,
    FROST_ON_MINUTES,
    HISTORY_MAX_SESSIONS,
    MAX_MINUTES_WITHOUT_SWEEP,
    MIN_DELTA_GAP,
    MIN_SUN_ELEVATION,
    MODE_AUTO,
    MODE_BOOST,
    MODE_VACATION,
    MODES,
    PROBLEM_LOW_YIELD,
    PROBLEM_LOW_YIELD_DELTA,
    PROBLEM_LOW_YIELD_SWEEPS,
    PROBLEM_LOW_YIELD_UV,
    PROBLEM_POOL_SENSOR,
    PROBLEM_PUMP,
    PROBLEM_PUMP_TIMEOUT_SECONDS,
    PROBLEM_RETURN_SENSOR,
    PROBLEM_RETURN_STUCK,
    PROBLEM_SENSOR_UNAVAILABLE_MINUTES,
    RL_ACTION_SWEEP,
    RL_ACTION_WAIT,
    STATE_COOLDOWN,
    STATE_COOLING,
    STATE_ERROR,
    STATE_FROST,
    STATE_HEATING,
    STATE_IDLE,
    STATE_MEASURING,
    STATE_SWEEPING,
    STATE_WAITING,
    STORAGE_VERSION,
    SWEEP_CHECK_SECONDS,
    SWEEP_FIRST_CHECK_SECONDS,
    SWEEP_MIN_SECONDS,
    SWEEP_STABLE_RANGE,
)
from .explanation_templates import ExplanationEngine
from .rl_agent import RLAgent

_LOGGER = logging.getLogger(__name__)

RETURN_STUCK_SWEEPS = 3  # barridos seguidos sin cambio del sensor de retorno


class SolarPoolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Máquina de estados de SolarPool AI."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Inicializa el coordinator (sin I/O: el Store se carga en async_start)."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,  # manejamos nuestros propios timers
        )
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")

        # ---- Estado público (leído por las entidades)
        self.state = STATE_IDLE
        self.reasoning = ""
        self.expected_gain = 0.0
        self.last_reward = 0.0
        self.enabled = True
        self.mode = MODE_AUTO
        self.next_cycle_time: datetime | None = None
        self.current_delta: float | None = None
        self.daily_gain = 0.0
        self.last_session: dict[str, Any] | None = None
        self.problems: set[str] = set()
        self.history: list[dict[str, Any]] = []
        self.rl_agent = RLAgent()

        self._language = self._conf(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        self.explanation_engine = ExplanationEngine(self._language)
        self.cycle_interval_minutes = int(self._conf(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.reasoning = self.explanation_engine.get_status_message("waiting_ha")

        # ---- Bomba (ownership: la bomba también filtra; solo apagamos lo que prendimos)
        self._pump_started_by_us = False
        self._pump_on_since: datetime | None = None
        self._expected_pump_state: str | None = None
        self._pump_cmd_time: datetime | None = None

        # ---- Sesión en curso (barrido + calentamiento) y seguimiento
        self._session: dict[str, Any] | None = None
        self._last_sweep_time: datetime | None = None
        self._day: dict[str, Any] = {}
        self._sweep_start_time: datetime | None = None
        self._sweep_readings: list[float] = []
        self._delta_readings: deque[float] = deque(maxlen=DELTA_MEDIAN_WINDOW)
        self._low_delta_count = 0
        self._heating_missing_reads = 0
        self._low_yield_count = 0
        self._return_stuck_count = 0
        self._unavailable_since: dict[str, datetime] = {}
        self._block_until: datetime | None = None  # fin del bloque ON (enfriamiento / antiheladas)
        self._frost_next_on: datetime | None = None

        # ---- Handles de timers / listeners
        self._unsub_interval: Callable[[], None] | None = None
        self._unsub_fast: Callable[[], None] | None = None
        self._unsub_pump: Callable[[], None] | None = None
        self._unsub_start: Callable[[], None] | None = None
        self._sweep_timer: Callable[[], None] | None = None
        self._off_timer: Callable[[], None] | None = None

    # ===================================================================== config
    def _conf(self, key: str, default: Any = None) -> Any:
        """Lee configuración: options → data → default.

        Un valor None explícito en options significa "borrado por el usuario".
        """
        if key in self.entry.options:
            value = self.entry.options[key]
            return default if value is None or value == "" else value
        value = self.entry.data.get(key, default)
        return default if value is None or value == "" else value

    @property
    def max_temp(self) -> float:
        """Temperatura máxima de la pileta."""
        return float(self._conf(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))

    @property
    def delta_on(self) -> float:
        """ΔT mínimo para empezar a calentar."""
        return float(self._conf(CONF_DELTA_ON, DEFAULT_DELTA_ON))

    @property
    def delta_off(self) -> float:
        """ΔT de corte (siempre al menos MIN_DELTA_GAP por debajo de delta_on)."""
        return min(float(self._conf(CONF_DELTA_OFF, DEFAULT_DELTA_OFF)), self.delta_on - MIN_DELTA_GAP)

    @property
    def session_active(self) -> bool:
        """Hay una sesión (barrido/calentamiento) en curso."""
        return self._session is not None

    # ================================================================ persistencia
    async def async_load(self) -> None:
        """Carga el estado persistido del Store."""
        data = await self._store.async_load() or {}
        self.rl_agent = RLAgent.from_dict(data.get("rl"))
        self.history = list(data.get("history") or [])
        self.last_session = self.history[-1] if self.history else None
        self.last_reward = float(data.get("last_reward") or 0.0)
        mode = data.get("mode", MODE_AUTO)
        self.mode = mode if mode in MODES else MODE_AUTO
        self._session = data.get("session")
        self._pump_started_by_us = bool(data.get("pump_owned", False))
        self._day = data.get("day") or {}
        if self._day.get("date") == dt_util.now().date().isoformat():
            self.daily_gain = float(self._day.get("gain") or 0.0)
        last_sweep = data.get("last_sweep")
        self._last_sweep_time = dt_util.parse_datetime(last_sweep) if last_sweep else None
        _LOGGER.info(
            "SolarPool: estado cargado (episodios RL=%d, sesiones=%d, modo=%s, bomba propia=%s)",
            self.rl_agent.episode_count, len(self.history), self.mode, self._pump_started_by_us,
        )

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Snapshot serializable para el Store."""
        return {
            "rl": self.rl_agent.to_dict(),
            "history": self.history[-HISTORY_MAX_SESSIONS:],
            "last_reward": self.last_reward,
            "mode": self.mode,
            "session": self._session,
            "pump_owned": self._pump_started_by_us,
            "day": self._day,
            "last_sweep": self._last_sweep_time.isoformat() if self._last_sweep_time else None,
        }

    @callback
    def _schedule_save(self) -> None:
        """Guardado diferido (agrupa escrituras)."""
        self._store.async_delay_save(self._data_to_save, 5)

    # =================================================================== ciclo de vida
    async def _async_update_data(self) -> dict[str, Any]:
        """Snapshot del estado (no hay polling)."""
        return {"state": self.state, "reasoning": self.reasoning}

    async def async_start(self) -> None:
        """Carga el Store, arranca timers y programa el primer ciclo."""
        await self.async_load()
        self._setup_interval()
        self._unsub_fast = async_track_time_interval(
            self.hass, self._async_fast_tick, timedelta(seconds=FAST_TICK_SECONDS)
        )
        pump = self._conf(CONF_PUMP_ENTITY_ID)
        if pump:
            self._unsub_pump = async_track_state_change_event(self.hass, [pump], self._async_pump_changed)

        if self.hass.is_running:
            _LOGGER.info("SolarPool AI inicializado, primer ciclo en 10 segundos")
            self._unsub_start = async_call_later(self.hass, 10, self._async_initial_run)
        else:
            _LOGGER.info("SolarPool AI inicializado, esperando que Home Assistant arranque...")

            @callback
            def _on_started(_event: Event) -> None:
                self._unsub_start = async_call_later(self.hass, 10, self._async_initial_run)

            self._unsub_start = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    async def _async_initial_run(self, _now: datetime | None = None) -> None:
        """Primer ciclo: retomar lo que quedó de antes del reinicio y evaluar."""
        self._unsub_start = None
        await self._async_resume_after_restart()
        await self.async_tick()

    async def _async_resume_after_restart(self) -> None:
        """Si antes del reinicio estábamos calentando con la bomba propia, retomar o apagar."""
        if not self._pump_started_by_us:
            if self._session:
                _LOGGER.info("SolarPool: descartando sesión incompleta de antes del reinicio")
                self._session = None
                self._schedule_save()
            return

        pump_on = self._pump_is_on()
        session = self._session
        can_resume = (
            pump_on
            and session is not None
            and session.get("heating_start") is not None
            and self.enabled
            and self.mode != MODE_VACATION
            and self._is_daytime_for_heating()
        )
        if can_resume:
            _LOGGER.info("SolarPool: retomando calentamiento tras reinicio")
            self._pump_on_since = dt_util.parse_datetime(session["sweep_start"]) or dt_util.utcnow()
            self._reset_heating_tracking()
            self._set_state(STATE_HEATING, self.explanation_engine.get_status_message("resumed_heating"))
            return

        _LOGGER.info("SolarPool: la bomba quedó a nuestro cargo antes del reinicio; apagándola")
        await self._async_end_session(aborted=True)
        if pump_on:
            await self._async_pump(False)
        self._pump_started_by_us = False
        self._schedule_save()

    async def async_stop(self) -> None:
        """Cancela timers/listeners, apaga la bomba si es nuestra y guarda el Store."""
        for attr in ("_unsub_interval", "_unsub_fast", "_unsub_pump", "_unsub_start", "_sweep_timer", "_off_timer"):
            unsub = getattr(self, attr)
            if unsub:
                try:
                    unsub()
                except ValueError:  # listen_once ya disparado
                    pass
                setattr(self, attr, None)
        if self.state in ACTIVE_PUMP_STATES or self._pump_started_by_us:
            await self._async_end_session(aborted=True)
            await self._async_pump(False)
            self._set_state(STATE_IDLE, self.explanation_engine.get_status_message("initializing"))
        await self._store.async_save(self._data_to_save())

    @callback
    def _setup_interval(self) -> None:
        """(Re)crea el tick lento."""
        if self._unsub_interval:
            self._unsub_interval()
        self._unsub_interval = async_track_time_interval(
            self.hass, self.async_tick, timedelta(minutes=self.cycle_interval_minutes)
        )
        self.next_cycle_time = dt_util.utcnow() + timedelta(minutes=self.cycle_interval_minutes)

    @callback
    def async_update_interval(self, minutes: int) -> None:
        """Cambia el intervalo del tick lento (solo si cambió)."""
        minutes = int(minutes)
        if minutes == self.cycle_interval_minutes and self._unsub_interval:
            return
        self.cycle_interval_minutes = minutes
        self._setup_interval()
        _LOGGER.info("SolarPool: intervalo actualizado a %s minutos", minutes)

    @callback
    def async_options_updated(self) -> None:
        """Aplica cambios de options (intervalo, idioma) sin recargar."""
        self.async_update_interval(int(self._conf(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        language = self._conf(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        if language != self._language:
            self._language = language
            self.explanation_engine = ExplanationEngine(language)
        self.async_update_listeners()

    # ============================================================== API entidades
    async def async_force_cycle(self) -> None:
        """Botón 'Forzar consulta'."""
        await self.async_tick(force=True)

    async def async_set_enabled(self, enabled: bool) -> None:
        """Switch Master: apagado total (incluye protecciones)."""
        self.enabled = enabled
        if enabled:
            await self.async_tick()
            return
        self._cancel_timer("_sweep_timer")
        self._cancel_timer("_off_timer")
        await self._async_end_session(aborted=True)
        await self._async_pump(False)
        self._block_until = None
        self._frost_next_on = None
        self._set_state(STATE_IDLE, self.explanation_engine.get_status_message("master_off"))

    async def async_set_mode(self, mode: str) -> None:
        """Selector de modo."""
        if mode not in MODES:
            return
        self.mode = mode
        self._schedule_save()
        if mode == MODE_VACATION:
            msg = self.explanation_engine.get_status_message("mode_vacation")
            if self.state == STATE_HEATING:
                await self._async_finish_heating(msg)
            elif self.state in (STATE_SWEEPING, STATE_MEASURING):
                self._cancel_timer("_sweep_timer")
                await self._async_end_session(aborted=True)
                await self._async_release_pump(STATE_IDLE, msg)
            elif self.state not in ACTIVE_PUMP_STATES:
                self._set_state(STATE_IDLE, msg)
        elif mode == MODE_BOOST and self.state not in ACTIVE_PUMP_STATES:
            await self.async_tick()
        self.async_update_listeners()

    # ================================================================== tick lento
    async def async_tick(self, _now: datetime | None = None, force: bool = False) -> None:
        """Ciclo principal: decide si barrer."""
        self.next_cycle_time = dt_util.utcnow() + timedelta(minutes=self.cycle_interval_minutes)
        if not self.enabled and not force:
            self.async_update_listeners()
            return
        if self.state in ACTIVE_PUMP_STATES:
            _LOGGER.debug("SolarPool: bomba en uso (%s), el tick rápido se encarga", self.state)
            self.async_update_listeners()
            return

        if not force:
            if not self._check_prerequisites():
                return
            if self.mode == MODE_VACATION:
                self._set_state(STATE_IDLE, self.explanation_engine.get_status_message("mode_vacation"))
                return

        context = self._gather_context(require_temps=False)
        if context is None:
            self._set_state(STATE_ERROR, self.explanation_engine.get_status_message("sensor_error"))
            return

        self.expected_gain = self.rl_agent.expected_gain(context, 60)
        pump_already_on = self._pump_is_on() and not self._pump_started_by_us
        if force or self.mode == MODE_BOOST or pump_already_on:
            decision = {
                "state": self.rl_agent.discretize_state(context),
                "action": RL_ACTION_SWEEP,
                "is_learning": False,
            }
        else:
            decision = self.rl_agent.get_action(context)
            if decision["action"] == RL_ACTION_WAIT and self._sweep_overdue():
                _LOGGER.info("SolarPool: hace más de %d min que no barremos, barrido de control", MAX_MINUTES_WITHOUT_SWEEP)
                decision["action"] = RL_ACTION_SWEEP

        if decision["action"] == RL_ACTION_WAIT:
            self._set_state(
                STATE_WAITING,
                self.explanation_engine.get_wait_explanation(context, self.expected_gain),
            )
            return

        await self._async_start_sweep(
            decision,
            context,
            forced=force,
            learn=not pump_already_on,
        )

    def _sweep_overdue(self) -> bool:
        if self._last_sweep_time is None:
            return True
        return dt_util.utcnow() - self._last_sweep_time >= timedelta(minutes=MAX_MINUTES_WITHOUT_SWEEP)

    def _check_prerequisites(self) -> bool:
        """Sol suficiente y pileta bajo la máxima. Actualiza el estado si no se cumplen."""
        sun = self.hass.states.get("sun.sun")
        if sun:
            if sun.state != "above_horizon":
                self._on_night()
                self._set_state(STATE_IDLE, self.explanation_engine.get_status_message("sun_below_horizon"))
                return False
            elevation = float(sun.attributes.get("elevation", 0) or 0)
            if elevation < MIN_SUN_ELEVATION:
                self._set_state(
                    STATE_IDLE,
                    self.explanation_engine.get_status_message("sun_too_low", elevation=elevation),
                )
                return False

        t_pool = self._read(CONF_POOL_SENSOR_ID)
        if t_pool is not None and t_pool >= self.max_temp:
            self._set_state(
                STATE_COOLDOWN,
                self.explanation_engine.get_status_message("max_temp_reached", temp=t_pool, max_temp=self.max_temp),
            )
            return False
        return True

    @callback
    def _on_night(self) -> None:
        """Cosas que pasan al caer el sol."""
        if self.mode == MODE_BOOST:
            _LOGGER.info("SolarPool: fin del día, modo boost vuelve a auto")
            self.mode = MODE_AUTO
            self._schedule_save()

    def _is_daytime_for_heating(self) -> bool:
        sun = self.hass.states.get("sun.sun")
        if sun is None:
            return True
        return sun.state == "above_horizon" and float(sun.attributes.get("elevation", 0) or 0) >= MIN_SUN_ELEVATION

    def _is_night(self) -> bool:
        sun = self.hass.states.get("sun.sun")
        return sun is not None and sun.state != "above_horizon"

    # ===================================================================== barrido
    async def _async_start_sweep(
        self, decision: dict[str, Any], context: dict[str, Any], forced: bool, learn: bool
    ) -> None:
        """Prende la bomba y empieza a vigilar la estabilidad del retorno."""
        self._cancel_timer("_off_timer")
        now = dt_util.utcnow()
        self._session = {
            "rl_state": decision["state"],
            "action": decision["action"],
            "learn": learn,
            "sweep_start": now.isoformat(),
            "heating_start": None,
            "t_pool_start": None,
            "delta_start": None,
            "uv": context.get("uv_index"),
            "wind": context.get("wind_speed"),
            "elevation": context.get("sun_elevation"),
        }
        self._last_sweep_time = now
        msg = self.explanation_engine.get_sweep_message(
            forced=forced,
            is_learning=decision.get("is_learning", False) and not self.rl_agent.is_bootstrap,
            is_bootstrap=self.rl_agent.is_bootstrap and not forced,
        )
        self._set_state(STATE_SWEEPING, msg)
        await self._async_pump(True)
        self._sweep_start_time = now
        self._sweep_readings = []
        self._sweep_timer = async_call_later(self.hass, SWEEP_FIRST_CHECK_SECONDS, self._async_check_sweep_stability)
        self._schedule_save()

    async def _async_check_sweep_stability(self, _now: datetime | None = None) -> None:
        """Análisis de ventana: estable si max-min < 0.2 °C tras >= 60 s y 3 lecturas."""
        self._sweep_timer = None
        if self.state != STATE_SWEEPING or self._sweep_start_time is None:
            return
        max_sweep = float(self._conf(CONF_SWEEP_DURATION, DEFAULT_SWEEP_DURATION))
        elapsed = (dt_util.utcnow() - self._sweep_start_time).total_seconds()

        t_return = self._read(CONF_RETURN_SENSOR_ID)
        is_stable = False
        if t_return is not None:
            self._sweep_readings.append(t_return)
            if elapsed >= SWEEP_MIN_SECONDS and len(self._sweep_readings) >= 3:
                spread = max(self._sweep_readings) - min(self._sweep_readings)
                if spread < SWEEP_STABLE_RANGE:
                    is_stable = True
                    _LOGGER.info("Barrido: estabilidad detectada (rango %.2f°C)", spread)

        if is_stable or elapsed >= max_sweep:
            await self._async_evaluate_sweep()
        else:
            self._sweep_timer = async_call_later(self.hass, SWEEP_CHECK_SECONDS, self._async_check_sweep_stability)

    async def _async_evaluate_sweep(self) -> None:
        """Mide ΔT tras el barrido y decide calentar o apagar."""
        self._set_state(STATE_MEASURING, self.explanation_engine.get_status_message("measuring_sensors"))
        context = self._gather_context(require_temps=True)
        if context is None:
            await self._async_end_session(aborted=True)
            await self._async_release_pump(STATE_ERROR, self.explanation_engine.get_status_message("sensor_error"))
            return

        t_pool = context["t_pool"]
        delta = context["t_return"] - t_pool
        self.current_delta = round(delta, 2)
        self._update_daily(t_pool)
        self._check_return_stuck()
        self._check_low_yield(context, delta)

        if self._session is not None:
            self._session["delta_start"] = round(delta, 2)

        if delta >= self.delta_on and t_pool < self.max_temp and self.mode != MODE_VACATION:
            if self._session is not None:
                self._session["heating_start"] = dt_util.utcnow().isoformat()
                self._session["t_pool_start"] = t_pool
            self._reset_heating_tracking()
            self._delta_readings.append(delta)
            self.expected_gain = self.rl_agent.expected_gain(context, 60)
            _LOGGER.info("SolarPool: ΔT=%.1f°C >= %.1f°C, calentando", delta, self.delta_on)
            self._set_state(STATE_HEATING, self.explanation_engine.get_heating_explanation(context))
            self._schedule_save()
            return

        _LOGGER.info("SolarPool: ΔT=%.1f°C < %.1f°C, no conviene calentar", delta, self.delta_on)
        reasoning = self.explanation_engine.get_off_explanation(context, self.delta_on)
        await self._async_end_session(heated=False)
        await self._async_release_pump(STATE_IDLE, reasoning)

    def _check_return_stuck(self) -> None:
        """Problema si el sensor de retorno no cambió en varios barridos seguidos."""
        eid = self._conf(CONF_RETURN_SENSOR_ID)
        state = self.hass.states.get(eid) if eid else None
        if state is None or self._sweep_start_time is None:
            return
        if state.last_changed < self._sweep_start_time - timedelta(minutes=30):
            self._return_stuck_count += 1
            if self._return_stuck_count >= RETURN_STUCK_SWEEPS:
                self._set_problem(PROBLEM_RETURN_STUCK)
        else:
            self._return_stuck_count = 0
            self._clear_problem(PROBLEM_RETURN_STUCK)

    def _check_low_yield(self, context: dict[str, Any], delta: float) -> None:
        """Problema si con mucho sol el ΔT es bajo en varios barridos seguidos."""
        if delta >= PROBLEM_LOW_YIELD_DELTA:
            self._low_yield_count = 0
            self._clear_problem(PROBLEM_LOW_YIELD)
        elif (context.get("uv_index") or 0) >= PROBLEM_LOW_YIELD_UV:
            self._low_yield_count += 1
            if self._low_yield_count >= PROBLEM_LOW_YIELD_SWEEPS:
                self._set_problem(PROBLEM_LOW_YIELD)

    # ============================================================== calentamiento
    @callback
    def _reset_heating_tracking(self) -> None:
        self._delta_readings.clear()
        self._low_delta_count = 0
        self._heating_missing_reads = 0

    async def _async_check_heating(self) -> None:
        """Chequeo de 60 s durante HEATING: ΔT con histéresis y cortes de seguridad."""
        t_pool = self._read(CONF_POOL_SENSOR_ID)
        t_return = self._read(CONF_RETURN_SENSOR_ID)
        if t_pool is None or t_return is None:
            self._heating_missing_reads += 1
            if self._heating_missing_reads >= 5:
                await self._async_finish_heating(self.explanation_engine.get_status_message("sensor_error"))
            return
        self._heating_missing_reads = 0

        self._delta_readings.append(t_return - t_pool)
        median = statistics.median(self._delta_readings)
        self.current_delta = round(median, 2)
        self._update_daily(t_pool)

        stop_msg: str | None = None
        if t_pool >= self.max_temp:
            stop_msg = self.explanation_engine.get_status_message(
                "max_temp_reached", temp=t_pool, max_temp=self.max_temp
            )
        elif not self._is_daytime_for_heating():
            stop_msg = self.explanation_engine.get_status_message("sun_below_horizon")
        elif self.mode == MODE_VACATION:
            stop_msg = self.explanation_engine.get_status_message("mode_vacation")
        else:
            self._low_delta_count = self._low_delta_count + 1 if median < self.delta_off else 0
            if self._low_delta_count >= DELTA_OFF_CONSECUTIVE:
                stop_msg = self.explanation_engine.get_status_message(
                    "heating_stopped_delta", delta=median, delta_off=self.delta_off
                )

        if stop_msg:
            await self._async_finish_heating(stop_msg, t_pool)
        else:
            self.async_update_listeners()

    async def _async_finish_heating(self, message: str, t_pool: float | None = None) -> None:
        """Cierra la sesión de calentamiento y libera la bomba."""
        if t_pool is None:
            t_pool = self._read(CONF_POOL_SENSOR_ID)
        await self._async_end_session(heated=True, t_pool_end=t_pool)
        await self._async_release_pump(STATE_IDLE, message)

    async def _async_end_session(
        self, heated: bool = False, t_pool_end: float | None = None, aborted: bool = False
    ) -> None:
        """Registra la sesión, calcula la recompensa y actualiza el agente."""
        session = self._session
        if session is None:
            return
        self._session = None
        now = dt_util.utcnow()
        sweep_start = dt_util.parse_datetime(session["sweep_start"]) or now
        pump_minutes = (now - sweep_start).total_seconds() / 60

        heating_minutes = 0.0
        gain = 0.0
        heating_start = session.get("heating_start")
        if heated and heating_start and t_pool_end is not None and session.get("t_pool_start") is not None:
            heating_minutes = (now - (dt_util.parse_datetime(heating_start) or now)).total_seconds() / 60
            gain = round(t_pool_end - session["t_pool_start"], 2)

        outcome = "aborted" if aborted else ("heated" if heated and heating_start else "low_delta")
        record: dict[str, Any] = {
            "start": session["sweep_start"],
            "end": now.isoformat(),
            "outcome": outcome,
            "pump_minutes": round(pump_minutes, 1),
            "heating_minutes": round(heating_minutes, 1),
            "gain": gain,
            "delta_start": session.get("delta_start"),
            "uv": session.get("uv"),
            "wind": session.get("wind"),
            "elevation": session.get("elevation"),
        }

        if not aborted and session.get("learn", True):
            reward = self.rl_agent.calculate_reward(outcome == "heated", gain, pump_minutes)
            self.rl_agent.update(session["rl_state"], session["action"], reward)
            if outcome == "heated" and heating_minutes >= 10:
                self.rl_agent.update_gain_rate(session["rl_state"], gain / (heating_minutes / 60))
            self.last_reward = reward
            record["reward"] = reward

        self.history.append(record)
        self.history = self.history[-HISTORY_MAX_SESSIONS:]
        self.last_session = record
        if outcome == "heated":
            self.hass.bus.async_fire(
                EVENT_SESSION_ENDED,
                {
                    "entry_id": self.entry.entry_id,
                    "gain": gain,
                    "heating_minutes": round(heating_minutes, 1),
                    "pump_minutes": round(pump_minutes, 1),
                    "daily_gain": self.daily_gain,
                },
            )
        self._schedule_save()

    async def _async_release_pump(self, state: str, reasoning: str) -> None:
        """Pasa a `state` y apaga la bomba respetando el tiempo mínimo de funcionamiento."""
        remaining = 0.0
        if self._pump_started_by_us and self._pump_on_since is not None:
            run_min = (dt_util.utcnow() - self._pump_on_since).total_seconds() / 60
            remaining = DEFAULT_MIN_RUN_TIME - run_min
        if remaining > 0.1:
            reasoning = f"{reasoning} {self.explanation_engine.get_status_message('pump_protect', minutes=math.ceil(remaining))}"
            self._set_state(state, reasoning)
            self._cancel_timer("_off_timer")
            self._off_timer = async_call_later(self.hass, remaining * 60, self._async_delayed_off)
            return
        self._set_state(state, reasoning)
        await self._async_pump(False)

    async def _async_delayed_off(self, _now: datetime | None = None) -> None:
        """Fin de la protección de tiempo mínimo."""
        self._off_timer = None
        if self.state not in ACTIVE_PUMP_STATES:
            await self._async_pump(False)

    # =============================================================== tick rápido
    async def _async_fast_tick(self, _now: datetime | None = None) -> None:
        """Chequeos de 60 s: problemas, calentamiento y protecciones."""
        self._check_sensor_availability()
        self._check_pump_command_timeout()
        if not self.enabled:
            return
        if self.state == STATE_HEATING:
            await self._async_check_heating()
            return
        if await self._async_handle_frost():
            return
        await self._async_handle_night_cooling()

    def _ambient_temp(self) -> float | None:
        """Temperatura ambiente: sensor configurado o atributo del weather."""
        value = self._read(CONF_AMBIENT_TEMP_SENSOR_ID)
        if value is not None:
            return value
        weather = self.hass.states.get(self._conf(CONF_WEATHER_ENTITY_ID) or "")
        if weather is None:
            return None
        try:
            temp = weather.attributes.get("temperature")
            return float(temp) if temp is not None else None
        except (TypeError, ValueError):
            return None

    async def _async_handle_frost(self) -> bool:
        """Antiheladas: circula 10 min cada 30 mientras el ambiente esté bajo el umbral.

        Returns True si la protección está a cargo de la bomba en este tick.
        """
        enabled = bool(self._conf(CONF_FROST_PROTECTION, False))
        threshold = float(self._conf(CONF_FROST_THRESHOLD, DEFAULT_FROST_THRESHOLD))
        ambient = self._ambient_temp()
        now = dt_util.utcnow()

        if self.state == STATE_FROST:
            if not enabled or (ambient is not None and ambient >= threshold + FROST_HYSTERESIS):
                await self._async_exit_protection(self.explanation_engine.get_status_message("frost_complete"))
                return False
            if self._block_until is not None and now >= self._block_until:
                await self._async_pump(False)
                self._block_until = None
                self._frost_next_on = now + timedelta(minutes=FROST_CYCLE_MINUTES - FROST_ON_MINUTES)
                self._set_state(
                    STATE_FROST,
                    self.explanation_engine.get_status_message("frost_pause", temp=ambient if ambient is not None else 0),
                )
            elif self._block_until is None and self._frost_next_on is not None and now >= self._frost_next_on:
                await self._async_pump(True)
                self._block_until = now + timedelta(minutes=FROST_ON_MINUTES)
                self._frost_next_on = None
                self._set_state(
                    STATE_FROST,
                    self.explanation_engine.get_status_message("frost_active", temp=ambient if ambient is not None else 0),
                )
            return True

        if not enabled or ambient is None or ambient >= threshold:
            return False
        if self.state in (STATE_SWEEPING, STATE_MEASURING, STATE_COOLING):
            return False

        _LOGGER.warning("SolarPool: antiheladas activado (ambiente %.1f°C < %.1f°C)", ambient, threshold)
        self._cancel_timer("_off_timer")
        self._set_state(STATE_FROST, self.explanation_engine.get_status_message("frost_active", temp=ambient))
        await self._async_pump(True)
        self._block_until = now + timedelta(minutes=FROST_ON_MINUTES)
        self._frost_next_on = None
        return True

    async def _async_handle_night_cooling(self) -> None:
        """Enfriamiento nocturno: usa los colectores como radiador si la pileta se pasó."""
        enabled = bool(self._conf(CONF_NIGHT_COOLING, False))
        now = dt_util.utcnow()

        if self.state == STATE_COOLING:
            t_pool = self._read(CONF_POOL_SENSOR_ID)
            ambient = self._ambient_temp()
            stop = not enabled or not self._is_night() or (t_pool is not None and t_pool <= self.max_temp)
            if not stop and self._block_until is not None and now >= self._block_until:
                still_useful = (
                    t_pool is not None and ambient is not None and ambient < t_pool - COOLING_AMBIENT_GAP
                )
                if still_useful:
                    self._block_until = now + timedelta(minutes=COOLING_BLOCK_MINUTES)
                else:
                    stop = True
            if stop:
                await self._async_exit_protection(self.explanation_engine.get_status_message("cooling_complete"))
            else:
                self.async_update_listeners()
            return

        if not enabled or not self._is_night():
            return
        if self.state not in (STATE_IDLE, STATE_WAITING, STATE_COOLDOWN, STATE_ERROR):
            return
        t_pool = self._read(CONF_POOL_SENSOR_ID)
        ambient = self._ambient_temp()
        if t_pool is None or ambient is None:
            return
        if t_pool > self.max_temp + COOLING_MARGIN and ambient < t_pool - COOLING_AMBIENT_GAP:
            _LOGGER.info("SolarPool: enfriamiento nocturno (pileta %.1f°C, ambiente %.1f°C)", t_pool, ambient)
            self._cancel_timer("_off_timer")
            self._set_state(
                STATE_COOLING,
                self.explanation_engine.get_status_message("cooling_active", temp=t_pool, max_temp=self.max_temp),
            )
            await self._async_pump(True)
            self._block_until = now + timedelta(minutes=COOLING_BLOCK_MINUTES)

    async def _async_exit_protection(self, message: str) -> None:
        """Sale de antiheladas / enfriamiento."""
        self._block_until = None
        self._frost_next_on = None
        self._set_state(STATE_IDLE, message)
        await self._async_pump(False)

    # ================================================================== problemas
    def _check_sensor_availability(self) -> None:
        now = dt_util.utcnow()
        for key, problem in ((CONF_POOL_SENSOR_ID, PROBLEM_POOL_SENSOR), (CONF_RETURN_SENSOR_ID, PROBLEM_RETURN_SENSOR)):
            eid = self._conf(key)
            if not eid:
                continue
            if self._read_entity(eid) is None:
                since = self._unavailable_since.setdefault(eid, now)
                if now - since >= timedelta(minutes=PROBLEM_SENSOR_UNAVAILABLE_MINUTES):
                    self._set_problem(problem)
            else:
                self._unavailable_since.pop(eid, None)
                self._clear_problem(problem)

    def _check_pump_command_timeout(self) -> None:
        if self._expected_pump_state is None or self._pump_cmd_time is None:
            return
        if dt_util.utcnow() - self._pump_cmd_time < timedelta(seconds=PROBLEM_PUMP_TIMEOUT_SECONDS):
            return
        state = self.hass.states.get(self._conf(CONF_PUMP_ENTITY_ID) or "")
        if state is not None and state.state == self._expected_pump_state:
            self._clear_problem(PROBLEM_PUMP)
        else:
            self._set_problem(PROBLEM_PUMP)
        self._expected_pump_state = None

    @callback
    def _set_problem(self, key: str) -> None:
        if key in self.problems:
            return
        self.problems.add(key)
        message = self.explanation_engine.get_problem_text(key)
        _LOGGER.warning("SolarPool: problema detectado: %s", message)
        self.hass.bus.async_fire(EVENT_PROBLEM, {"entry_id": self.entry.entry_id, "problem": key, "message": message})
        self.async_update_listeners()

    @callback
    def _clear_problem(self, key: str) -> None:
        if key in self.problems:
            self.problems.discard(key)
            _LOGGER.info("SolarPool: problema resuelto: %s", key)
            self.async_update_listeners()

    # ===================================================================== bomba
    def _pump_is_on(self) -> bool:
        state = self.hass.states.get(self._conf(CONF_PUMP_ENTITY_ID) or "")
        return state is not None and state.state == STATE_ON

    async def _async_pump(self, turn_on: bool) -> None:
        """Controla la bomba compartida: solo apaga lo que SolarPool prendió."""
        pump = self._conf(CONF_PUMP_ENTITY_ID)
        if not pump:
            _LOGGER.error("SolarPool: no hay bomba configurada")
            return
        is_on = self._pump_is_on()

        if turn_on:
            if is_on:
                if not self._pump_started_by_us:
                    _LOGGER.debug("Bomba %s ya encendida (filtrado?), se usa sin tomar propiedad", pump)
                return
            _LOGGER.info("Encendiendo bomba %s (SolarPool)", pump)
            self._pump_started_by_us = True
            self._pump_on_since = dt_util.utcnow()
            self._schedule_save()
            await self._async_call_pump(pump, SERVICE_TURN_ON, STATE_ON)
            return

        if not is_on:
            self._pump_started_by_us = False
            self._pump_on_since = None
            self._schedule_save()
            return
        if self._pump_started_by_us:
            _LOGGER.info("Apagando bomba %s (la había prendido SolarPool)", pump)
            self._pump_started_by_us = False
            self._pump_on_since = None
            self._schedule_save()
            await self._async_call_pump(pump, SERVICE_TURN_OFF, STATE_OFF)
        else:
            _LOGGER.info("Bomba %s no fue prendida por SolarPool (filtrado?), se deja encendida", pump)
            self._pump_on_since = None

    async def _async_call_pump(self, pump: str, service: str, expected: str) -> None:
        self._expected_pump_state = expected
        self._pump_cmd_time = dt_util.utcnow()
        try:
            await self.hass.services.async_call(pump.split(".")[0], service, {"entity_id": pump}, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.error("SolarPool: error controlando la bomba %s: %s", pump, err)
            self._expected_pump_state = None
            self._set_problem(PROBLEM_PUMP)

    @callback
    def _async_pump_changed(self, event: Event) -> None:
        """Detecta respuesta a nuestros comandos y apagados externos."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        if self._expected_pump_state is not None and new_state.state == self._expected_pump_state:
            self._expected_pump_state = None
            self._clear_problem(PROBLEM_PUMP)
            return
        if (
            new_state.state == STATE_OFF
            and self.state in ACTIVE_PUMP_STATES
            and self._expected_pump_state != STATE_OFF
            and not (self.state == STATE_FROST and self._block_until is None)
        ):
            self.hass.async_create_task(self._async_external_pump_off())

    async def _async_external_pump_off(self) -> None:
        """Alguien apagó la bomba mientras la usábamos: soltarla y no pelearla."""
        _LOGGER.info("SolarPool: la bomba fue apagada externamente durante %s", self.state)
        self._cancel_timer("_sweep_timer")
        self._cancel_timer("_off_timer")
        await self._async_end_session(aborted=True)
        self._pump_started_by_us = False
        self._pump_on_since = None
        self._block_until = None
        self._frost_next_on = None
        self._schedule_save()
        self._set_state(STATE_IDLE, self.explanation_engine.get_status_message("pump_external_off"))

    # ================================================================== sensores
    def _read_entity(self, entity_id: str | None) -> float | None:
        """Valor numérico de una entidad (None si no existe / no disponible)."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _read(self, conf_key: str) -> float | None:
        """Valor numérico de la entidad configurada en `conf_key`."""
        return self._read_entity(self._conf(conf_key))

    @callback
    def _update_daily(self, t_pool: float) -> None:
        """Ganancia del día. Solo se llama con la bomba en marcha (lectura confiable)."""
        today = dt_util.now().date().isoformat()
        if self._day.get("date") != today:
            self._day = {"date": today, "t_start": t_pool, "gain": 0.0}
            _LOGGER.info("SolarPool: inicio de seguimiento diario (pileta %.1f°C)", t_pool)
        self.daily_gain = round(max(0.0, t_pool - float(self._day["t_start"])), 2)
        self._day["gain"] = self.daily_gain

    @staticmethod
    def _estimate_uv_from_elevation(elevation: float) -> float:
        """UV aproximado ≈ 12·sin(elevación) cuando no hay sensor ni atributo."""
        if elevation <= 0:
            return 0.0
        return round(max(0.0, min(12.0, 12.0 * math.sin(math.radians(elevation)))), 1)

    @staticmethod
    def _solar_hour_offset(sun_state: State | None) -> float:
        """Horas respecto del mediodía solar (negativo = mañana)."""
        if sun_state is None:
            return 0.0
        next_noon = sun_state.attributes.get("next_noon")
        noon = next_noon if isinstance(next_noon, datetime) else (
            dt_util.parse_datetime(next_noon) if isinstance(next_noon, str) else None
        )
        if noon is not None:
            diff_h = (dt_util.utcnow() - noon).total_seconds() / 3600
            if diff_h < -12:
                diff_h += 24  # el próximo mediodía es mañana → ya pasó el de hoy
            return round(diff_h, 2)
        rising = sun_state.attributes.get("rising")
        if rising is None:
            return 0.0
        return -3.0 if rising else 3.0

    def _gather_context(self, require_temps: bool) -> dict[str, Any] | None:
        """Reúne clima, sol y (opcionalmente) temperaturas."""
        weather_state = self.hass.states.get(self._conf(CONF_WEATHER_ENTITY_ID) or "")
        if weather_state is None:
            _LOGGER.error("SolarPool: entidad de clima no encontrada")
            return None

        sun = self.hass.states.get("sun.sun")
        sun_elevation = float(sun.attributes.get("elevation", 0) or 0) if sun else 0.0
        sun_azimuth = float(sun.attributes.get("azimuth", 0) or 0) if sun else 0.0

        # Nubes: sensor > atributo del weather
        cloud = self._read(CONF_CLOUD_COVERAGE_SENSOR_ID)
        if cloud is None:
            cloud = weather_state.attributes.get("cloud_coverage", 0)
        try:
            cloud_coverage = max(0.0, min(100.0, float(cloud or 0)))
        except (TypeError, ValueError):
            cloud_coverage = 0.0

        # UV: sensor > atributo > estimación por elevación (un 0 real es válido)
        uv_raw = self._read(CONF_UV_SENSOR_ID)
        uv_source = "sensor"
        if uv_raw is None:
            attr = weather_state.attributes.get("uv_index")
            uv_raw = float(attr) if isinstance(attr, (int, float)) else None
            uv_source = "weather"
        if uv_raw is None:
            uv_raw = self._estimate_uv_from_elevation(sun_elevation)
            uv_source = "estimated"
        # Penalización por nubes: factor = max(0.15, 1 - 0.85·nubes/100)
        if cloud_coverage > 0 and uv_source != "estimated":
            uv_index = round(uv_raw * max(0.15, 1 - 0.85 * cloud_coverage / 100), 1)
        else:
            uv_index = uv_raw

        wind = self._read(CONF_WIND_SENSOR_ID)
        if wind is None:
            try:
                wind = float(weather_state.attributes.get("wind_speed", 0) or 0)
            except (TypeError, ValueError):
                wind = 0.0

        context: dict[str, Any] = {
            "weather_state": weather_state.state,
            "temperature_ext": self._ambient_temp(),
            "wind_speed": wind,
            "uv_index": uv_index,
            "uv_index_raw": uv_raw,
            "uv_source": uv_source,
            "cloud_coverage": cloud_coverage,
            "sun_elevation": sun_elevation,
            "sun_azimuth": sun_azimuth,
            "solar_hour_offset": self._solar_hour_offset(sun),
        }

        if require_temps:
            t_pool = self._read(CONF_POOL_SENSOR_ID)
            t_return = self._read(CONF_RETURN_SENSOR_ID)
            if t_pool is None or t_return is None:
                _LOGGER.error("SolarPool: sensores de temperatura no disponibles")
                return None
            context["t_pool"] = t_pool
            context["t_return"] = t_return
        return context

    # ==================================================================== helpers
    @callback
    def _set_state(self, state: str, reasoning: str) -> None:
        """Actualiza estado + razonamiento (máx 255 caracteres) y notifica entidades."""
        self.state = state
        self.reasoning = reasoning[:252] + "..." if len(reasoning) > 255 else reasoning
        self.async_update_listeners()

    @callback
    def _cancel_timer(self, attr: str) -> None:
        unsub = getattr(self, attr)
        if unsub:
            unsub()
            setattr(self, attr, None)
