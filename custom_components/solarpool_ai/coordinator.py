"""DataUpdateCoordinator for SolarPool AI integration."""
from __future__ import annotations

import logging
import asyncio
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_ON,
    STATE_OFF,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import utcnow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval, async_call_later

from .const import (
    DOMAIN,
    CONF_PUMP_ENTITY_ID,
    CONF_POOL_SENSOR_ID,
    CONF_RETURN_SENSOR_ID,
    CONF_WEATHER_ENTITY_ID,
    CONF_UV_SENSOR_ID,
    CONF_WIND_SENSOR_ID,
    CONF_AMBIENT_TEMP_SENSOR_ID,
    CONF_CLOUD_COVERAGE_SENSOR_ID,
    CONF_SWEEP_DURATION,
    CONF_MAX_TEMP,
    CONF_SCAN_INTERVAL,
    CONF_CYCLE_HISTORY,
    CONF_Q_TABLE,
    CONF_RL_EPISODE_COUNT,
    CONF_LANGUAGE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SWEEP_DURATION,
    DEFAULT_LANGUAGE,
    STATE_IDLE,
    STATE_SWEEPING,
    STATE_MEASURING,
    STATE_CONSULTING,
    STATE_HEATING,
    STATE_COOLDOWN,
    STATE_ERROR,
)
from .rl_agent import RLAgent
from .explanation_templates import ExplanationEngine

_LOGGER = logging.getLogger(__name__)

# We no longer use a global SCAN_INTERVAL constant for the timer

class SolarPoolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the AI and sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We manage our own intervals
        )
        self.entry = entry
        self.state = STATE_IDLE
        self.reasoning = "Iniciando sistema..."
        self.expected_gain = 0.0
        self.last_reward = 0.0
        self.error_active = False
        self.enabled = True
        self.next_cycle_time: datetime | None = None
        
        # Daily yield tracking
        self.t_pool_day_start: float | None = None
        self.daily_gain: float = 0.0
        
        # Get interval from config
        self.cycle_interval_minutes = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        
        # Load cycle history from config_entry
        self.cycle_history = entry.data.get(CONF_CYCLE_HISTORY, [])
        self.current_cycle_data = None  # Datos del ciclo en curso
        
        # Initialize RL Agent and Explanation Engine
        self._init_rl_agent()
    
    def _init_rl_agent(self) -> None:
        """Initialize or reinitialize the RL agent based on current config."""
        entry = self.entry
        
        # Load RL agent state from config_entry if available
        q_table = entry.data.get(CONF_Q_TABLE)
        episode_count = entry.data.get(CONF_RL_EPISODE_COUNT, 0)
        
        self.rl_agent = RLAgent(
            q_table=q_table,
            episode_count=episode_count,
        )
        _LOGGER.info(
            "RL Agent initialized: episodes=%d, warmup=%s, exploration=%.2f",
            self.rl_agent.episode_count,
            self.rl_agent.is_warmup,
            self.rl_agent.exploration_rate,
        )
        
        # Initialize explanation engine with language from config
        language = entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE))
        self.explanation_engine = ExplanationEngine(language)
        
        # Seguimiento de intervalos y temporizadores
        self._unsub_interval = None
        self._sweep_timer = None
        self._heating_timer = None  # Timer para apagar la bomba después de heating_duration
        
        # Lógica de 'Ownership' (Propiedad) de la bomba
        # Evita apagar la bomba si ya estaba encendida por otro proceso (ej. filtrado)
        self._pump_started_by_us = False  # Indica si NOSOTROS encendimos la bomba
        
        # Seguimiento del estado de calefacción
        self.pump_is_heating = False
        self.heating_start_time: datetime | None = None
        self._last_pump_on_time: datetime | None = None  # Tiempo total físico de bomba encendida
        self.heating_duration_minutes = 0
        
        # Daily cycle tracking
        self.is_daytime_active = False
        self.first_cycle_of_day = True
        
        # Stability tracking during sweep
        self._sweep_start_time: datetime | None = None
        self._sweep_readings: list[float] = []
        self._last_sweep_t_return: float | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and AI."""
        # This is called manually or via automation
        return {
            "state": self.state,
            "reasoning": self.reasoning,
            "expected_gain": self.expected_gain,
            "error_active": self.error_active,
        }

    @callback
    def _async_setup_listeners(self):
        """Configura los oyentes periódicos (el bucle principal)."""
        if self._unsub_interval:
            self._unsub_interval() # Cancelar si ya existe uno
            
        # Ejecuta async_start_cycle cada N minutos según configuración
        self._unsub_interval = async_track_time_interval(
            self.hass, self.async_start_cycle, timedelta(minutes=self.cycle_interval_minutes)
        )

    @callback
    def async_update_interval(self, minutes: int):
        """Update the scan interval."""
        self.cycle_interval_minutes = minutes
        self._async_setup_listeners()
        # Also schedule next run based on new interval
        self.next_cycle_time = utcnow() + timedelta(minutes=minutes)
        _LOGGER.info("SolarPool interval updated to %s minutes", minutes)

    async def async_config_entry_first_refresh(self) -> None:
        """Set up the coordinator and start the first cycle."""
        # Reset state on startup in case previous run left it in an inconsistent state
        self.state = STATE_IDLE
        self.reasoning = self.explanation_engine.get_status_message("waiting_ha")
        self.pump_is_heating = False
        self.heating_start_time = None
        self.heating_duration_minutes = 0
        
        self._async_setup_listeners()
        
        # Wait for Home Assistant to fully start before running first cycle
        if self.hass.is_running:
            # HA already running, start cycle after short delay
            _LOGGER.info("SolarPool AI initialized, first cycle in 10 seconds")
            async_call_later(self.hass, 10, self.async_start_cycle)
        else:
            # Wait for HA to fully start
            _LOGGER.info("SolarPool AI initialized, waiting for Home Assistant to start...")
            
            async def _start_after_ha_ready(event):
                _LOGGER.info("Home Assistant started, beginning first cycle in 10 seconds")
                await asyncio.sleep(10)  # Additional delay to ensure entities are ready
                await self.async_start_cycle()
            
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start_after_ha_ready)

    async def async_start_cycle(self, _now: datetime | None = None, force: bool = False) -> None:
        """Inicia un ciclo completo: Chequeo -> Barrido -> IA -> Calentamiento."""
        if not self.enabled and not force:
            _LOGGER.debug("SolarPool está deshabilitado, omitiendo ciclo")
            return

        _LOGGER.debug("Iniciando ciclo SolarPool (forzado=%s)", force)
        
        # Calculamos la próxima ejecución para el sensor
        self.next_cycle_time = utcnow() + timedelta(minutes=self.cycle_interval_minutes)

        # 1. Chequeo de requisitos (Sol alto, Temperatura máx, etc.)
        if not force and not await self._async_check_prerequisites():
            return

        # 2. FASE DE BARRIDO (Sweep)
        # Si la bomba ya está prendida por nosotros (proceso continuo), saltamos el barrido
        if self.pump_is_heating:
            _LOGGER.info("Bomba ya en funcionamiento, saltando barrido para consulta instantánea")
            await self._async_measure_and_consult()
        else:
            _LOGGER.info("Iniciando fase de barrido (sweep)")
            msg = self.explanation_engine.get_status_message("sweep_forced") if force else self.explanation_engine.get_status_message("sweep_starting")
            await self._async_set_state(STATE_SWEEPING, msg)
            
            # Encendemos bomba (con protección de ownership)
            await self._async_control_pump(True)
            
            # Inicializamos limpieza de datos para análisis de estabilidad
            self._sweep_start_time = utcnow()
            self._sweep_readings = []
            self._last_sweep_t_return = None
            
            # Programamos el primer chequeo de estabilidad en 30 segundos
            self._sweep_timer = async_call_later(self.hass, 30, self._async_check_sweep_stability)

    async def _async_check_sweep_stability(self, _now: datetime | None = None) -> None:
        """Analiza la temperatura de retorno para detectar estabilidad (Análisis de Ventana)."""
        if self.state != STATE_SWEEPING:
            return

        # Duración máxima configurada por el usuario
        max_sweep_duration = self.entry.options.get(
            CONF_SWEEP_DURATION, 
            self.entry.data.get(CONF_SWEEP_DURATION, DEFAULT_SWEEP_DURATION)
        )
        
        elapsed = (utcnow() - self._sweep_start_time).total_seconds()
        
        # Leer sensor de retorno
        return_sensor = self.entry.data.get(CONF_RETURN_SENSOR_ID)
        current_t_return = None
        if return_sensor:
            state = self.hass.states.get(return_sensor)
            if state and state.state not in ["unknown", "unavailable"]:
                try:
                    current_t_return = float(state.state)
                except ValueError:
                    pass

        # ALGORITMO DE VARIACIÓN:
        # Acumula lecturas y verifica que la diferencia entre Max y Min sea < 0.2°C
        is_stable = False
        if current_t_return is not None:
            self._sweep_readings.append(current_t_return)
            
            if elapsed >= 60 and len(self._sweep_readings) >= 3:
                window_min = min(self._sweep_readings)
                window_max = max(self._sweep_readings)
                rango = window_max - window_min
                
                if rango < 0.2:
                    is_stable = True
                    _LOGGER.info("Barrido: Estabilidad detectada (Rango: %.2f°C)", rango)
        
        # Si está estable O se acabó el tiempo, procedemos a consultar a la IA
        if is_stable or elapsed >= max_sweep_duration:
            await self._async_measure_and_consult()
        else:
            # Re-programar chequeo en 15 segundos
            self._sweep_timer = async_call_later(self.hass, 15, self._async_check_sweep_stability)

    async def _async_measure_and_consult(self, _now: datetime | None = None) -> None:
        """Step 3 & 4: Measure and Consult RL Agent."""
        status_msg = self.explanation_engine.get_status_message("measuring_sensors")
        await self._async_set_state(STATE_MEASURING, status_msg)
        
        context = await self._async_gather_context()
        if not context:
            error_msg = self.explanation_engine.get_status_message("sensor_error")
            await self._async_set_state(STATE_IDLE, error_msg)
            await self._async_control_pump(False)
            return

        # 4. CONSULTING RL AGENT (instantaneous, no API call)
        consulting_msg = self.explanation_engine.get_status_message("consulting_ai")
        await self._async_set_state(STATE_CONSULTING, consulting_msg)
        
        decision = self.rl_agent.get_action(context)
        
        action = decision.get("action", "OFF")
        expected_gain = decision.get("expected_gain", 0.0)
        heating_duration = decision.get("heating_duration_minutes", 0)
        is_learning = decision.get("is_learning", False)
        is_warmup = decision.get("is_warmup", False)
        
        # Generate human-readable explanation using templates
        self.reasoning = self.explanation_engine.get_explanation(
            action=action,
            context=context,
            is_learning=is_learning,
            is_warmup=is_warmup,
        )
        self.expected_gain = expected_gain
        
        _LOGGER.info(
            "RL Decision: %s for %d min (gain=%.1f°C, learning=%s, warmup=%s)",
            action, heating_duration, expected_gain, is_learning, is_warmup
        )

        # --- SAFETY OVERRIDE & HYSTERESIS ---
        actual_delta = context["t_return"] - context["t_pool"]
        
        # Protection: Minimum run time to prevent short-cycling (Sweep + Heating)
        if action == "OFF" and self._last_pump_on_time:
            run_time_min = (utcnow() - self._last_pump_on_time).total_seconds() / 60
            from .const import DEFAULT_MIN_RUN_TIME
            if run_time_min < DEFAULT_MIN_RUN_TIME:
                remaining_min = DEFAULT_MIN_RUN_TIME - run_time_min
                _LOGGER.info("Protección: IA sugirió OFF pero bomba lleva solo %.1f min. Manteniendo ON por %.1f min más.", 
                            run_time_min, remaining_min)
                action = "ON"
                heating_duration = int(remaining_min) + 2 # Agregamos 2 min de margen
                self.reasoning += f" (Protegiendo bomba: {run_time_min:.0f}min run)"

        # Safety: Delta T too low
        if action == "ON" and actual_delta < 2.0:
            _LOGGER.warning(
                "RL sugirió ON con un diferencial real de %.1f°C. Forzando OFF por eficiencia.",
                actual_delta
            )
            action = "OFF"
            heating_duration = 0
            override_msg = self.explanation_engine.get_status_message("safety_override", delta=actual_delta)
            self.reasoning = override_msg
        # ----------------------------------------

        # Guardar datos del ciclo actual para el historial y RL feedback
        self.current_cycle_data = {
            "timestamp": utcnow().isoformat(),
            "conditions": context.copy(),
            "decision": action,
            "expected_delta": expected_gain,
            "t_pool_start": context["t_pool"],
            "heating_duration": heating_duration,
            "is_learning": is_learning,
        }

        # 5. EXECUTING
        if action == "ON":
            await self._async_set_state(STATE_HEATING, self.reasoning)
            await self._async_control_pump(True)
            self.pump_is_heating = True
            self.heating_start_time = utcnow()
            self.heating_duration_minutes = heating_duration
            
            # Programar apagado automático después de heating_duration
            if self._heating_timer:
                self._heating_timer()  # Cancelar timer anterior si existe
            
            self._heating_timer = async_call_later(
                self.hass, 
                heating_duration * 60,  # Convertir minutos a segundos
                self._async_stop_heating
            )
            _LOGGER.info("Bomba encendida por %d minutos (ganancia esperada: %.1f°C)", heating_duration, expected_gain)
        else:
            await self._async_set_state(STATE_IDLE, self.reasoning)
            await self._async_control_pump(False)
            self.pump_is_heating = False
            
        # Actualizar historial con ganancia real si hay ciclo previo
        await self._async_update_cycle_history(context["t_pool"])

    async def _async_check_prerequisites(self) -> bool:
        """Check if we should run the cycle."""
        # 1. Master switch (manual override) - we'll check this via entity state later if needed
        # but for now, we assume if coordinator is running, it's active.
        
        # 2. Sun check (only run during day and meaningful elevation)
        sun_state = self.hass.states.get("sun.sun")
        if sun_state:
            if sun_state.state != "above_horizon":
                _LOGGER.debug("Sun is down, skipping cycle")
                # Reset daily tracking when sun goes down
                self.t_pool_day_start = None
                self.daily_gain = 0.0
                await self._async_set_state(STATE_IDLE, self.explanation_engine.get_status_message("sun_below_horizon"))
                await self._async_control_pump(False)
                return False
            
            elevation = sun_state.attributes.get("elevation", 0)
            if elevation < 5:
                _LOGGER.debug("Sun elevation too low (%s), skipping cycle", elevation)
                await self._async_set_state(STATE_IDLE, self.explanation_engine.get_status_message("sun_too_low", elevation=elevation))
                await self._async_control_pump(False)
                return False

        # 3. Max Temp check
        max_temp = self.entry.data.get(CONF_MAX_TEMP, 32.0)
        pool_sensor = self.entry.data.get(CONF_POOL_SENSOR_ID)
        pool_temp_state = self.hass.states.get(pool_sensor)
        
        if pool_temp_state and pool_temp_state.state not in ["unknown", "unavailable"]:
            try:
                temp = float(pool_temp_state.state)
                
                # Update daily gain tracking
                if self.t_pool_day_start is None:
                    # First reading of the day when sun is up and system is active
                    self.t_pool_day_start = temp
                    self.daily_gain = 0.0
                    _LOGGER.info("Starting daily yield tracking. Initial pool temp: %.1f°C", temp)
                else:
                    # Calculate current yield relative to start of day
                    # We use max(0, ...) to avoid negative values if pool cools down initially
                    self.daily_gain = round(max(0.0, temp - self.t_pool_day_start), 2)

                if temp >= max_temp:
                    await self._async_set_state(STATE_COOLDOWN, self.explanation_engine.get_status_message("max_temp_reached", temp=temp, max_temp=max_temp))
                    await self._async_control_pump(False)
                    return False
            except ValueError:
                pass

        return True

    def _estimate_uv_from_elevation(self, elevation: float) -> float:
        """Estimate UV index from sun elevation when no sensor data is available.
        
        This is a rough approximation based on the relationship between
        sun elevation angle and UV intensity. The formula accounts for:
        - UV is 0 when sun is below horizon or very low
        - UV increases with sin(elevation) due to shorter atmospheric path
        - Peak UV occurs around solar noon (highest elevation)
        
        Note: This doesn't account for clouds, ozone, or altitude.
        A dedicated UV sensor is always preferred.
        """
        if elevation <= 0:
            return 0.0
        
        # Convert elevation to radians for sin calculation
        elevation_rad = math.radians(elevation)
        
        # Basic formula: UV ≈ 12 * sin(elevation)
        # This gives approximately:
        # - elevation 10° → UV ≈ 2.1
        # - elevation 30° → UV ≈ 6.0
        # - elevation 50° → UV ≈ 9.2
        # - elevation 70° → UV ≈ 11.3
        # - elevation 90° → UV ≈ 12.0
        estimated_uv = 12.0 * math.sin(elevation_rad)
        
        # Clamp to reasonable range (0-12)
        return round(max(0.0, min(12.0, estimated_uv)), 1)

    def _get_sensor_value(self, sensor_id: str | None, default: float | None = None) -> float | None:
        """Get a numeric value from a sensor entity."""
        if not sensor_id:
            return default
        
        state = self.hass.states.get(sensor_id)
        if state and state.state not in ["unknown", "unavailable"]:
            try:
                return float(state.state)
            except (ValueError, TypeError):
                pass
        return default

    async def _async_gather_context(self) -> dict[str, Any] | None:
        """Gather all required sensor data for the AI."""
        try:
            pool_sensor = self.entry.data.get(CONF_POOL_SENSOR_ID)
            return_sensor = self.entry.data.get(CONF_RETURN_SENSOR_ID)
            weather_entity = self.entry.data.get(CONF_WEATHER_ENTITY_ID)

            pool_state = self.hass.states.get(pool_sensor)
            return_state = self.hass.states.get(return_sensor)
            weather_state = self.hass.states.get(weather_entity)

            if not (pool_state and return_state and weather_state):
                _LOGGER.error("One or more entities not found")
                return None

            # Gather sun data
            sun_state_obj = self.hass.states.get("sun.sun")
            sun_elevation = sun_state_obj.attributes.get("elevation", 0) if sun_state_obj else 0
            sun_azimuth = sun_state_obj.attributes.get("azimuth", 0) if sun_state_obj else 0

            # Get optional sensor overrides (from options first, then data for backwards compat)
            uv_sensor = self.entry.options.get(CONF_UV_SENSOR_ID, self.entry.data.get(CONF_UV_SENSOR_ID))
            cloud_sensor = self.entry.options.get(CONF_CLOUD_COVERAGE_SENSOR_ID, self.entry.data.get(CONF_CLOUD_COVERAGE_SENSOR_ID))
            wind_sensor = self.entry.options.get(CONF_WIND_SENSOR_ID, self.entry.data.get(CONF_WIND_SENSOR_ID))
            ambient_sensor = self.entry.options.get(CONF_AMBIENT_TEMP_SENSOR_ID, self.entry.data.get(CONF_AMBIENT_TEMP_SENSOR_ID))

            # Cloud coverage: Get from sensor if configured
            cloud_coverage = self._get_sensor_value(cloud_sensor)
            if cloud_coverage is None:
                # Try weather entity attributes (some weather integrations have this)
                cloud_coverage = weather_state.attributes.get("cloud_coverage", 0)
            
            # Clamp cloud coverage to 0-100 range
            cloud_coverage = max(0, min(100, cloud_coverage or 0))

            # UV Index: Priority is sensor > weather attribute > estimation
            # IMPORTANT: If a sensor returns 0, that's valid data (cloudy day), don't override!
            uv_index_raw = self._get_sensor_value(uv_sensor)
            uv_source = "sensor" if uv_index_raw is not None else None
            
            if uv_index_raw is None:
                uv_index_raw = weather_state.attributes.get("uv_index")
                uv_source = "weather" if uv_index_raw is not None else None
            
            # Only estimate if we have NO data at all (None), not if value is 0
            if uv_index_raw is None:
                uv_index_raw = self._estimate_uv_from_elevation(sun_elevation)
                uv_source = "estimated"
                _LOGGER.debug("UV estimated from elevation (%.1f°): %.1f", sun_elevation, uv_index_raw)
            
            # Apply cloud coverage penalty to UV
            # Scientific basis: clouds reduce UV but not completely
            # - 0% clouds: 100% UV transmission
            # - 50% clouds: ~57% UV transmission  
            # - 82% clouds: ~30% UV transmission
            # - 100% clouds: ~15% UV transmission (always some diffuse UV)
            # Formula: cloud_factor = max(0.15, 1 - (0.85 × cloud_coverage/100))
            if cloud_coverage > 0 and uv_source != "estimated":
                cloud_factor = max(0.15, 1 - (0.85 * cloud_coverage / 100))
                uv_index = round(uv_index_raw * cloud_factor, 1)
                _LOGGER.debug(
                    "UV from %s: %.1f, clouds: %.0f%%, factor: %.2f, UV effective: %.1f",
                    uv_source, uv_index_raw, cloud_coverage, cloud_factor, uv_index
                )
            else:
                uv_index = uv_index_raw
                if cloud_coverage == 0:
                    _LOGGER.debug("UV from %s: %.1f (clear sky)", uv_source, uv_index)
                else:
                    _LOGGER.debug("UV from %s: %.1f", uv_source, uv_index)

            # Wind speed: Priority is sensor > weather attribute
            wind_speed = self._get_sensor_value(wind_sensor)
            if wind_speed is None:
                wind_speed = weather_state.attributes.get("wind_speed", 0)

            # Ambient temperature: Priority is sensor > weather attribute
            temperature_ext = self._get_sensor_value(ambient_sensor)
            if temperature_ext is None:
                temperature_ext = weather_state.attributes.get("temperature")

            return {
                "t_pool": float(pool_state.state),
                "t_return": float(return_state.state),
                "weather_state": weather_state.state,
                "temperature_ext": temperature_ext,
                "wind_speed": wind_speed,
                "uv_index": uv_index,
                "uv_index_raw": uv_index_raw,
                "cloud_coverage": cloud_coverage,
                "sun_elevation": sun_elevation,
                "sun_azimuth": sun_azimuth,
                "performance_history": self._get_performance_summary(),
            }
        except (ValueError, TypeError) as err:
            _LOGGER.error("Error parsing sensor data: %s", err)
            return None

    def _get_performance_summary(self) -> list[dict[str, Any]]:
        """Get a summary of recent cycle performance for the AI."""
        summary = []
        for cycle in self.cycle_history[-5:]:  # Últimos 5 ciclos
            if cycle.get("actual_gain") is not None:
                efficiency = 0
                if cycle.get("expected_delta", 0) > 0:
                    efficiency = int((cycle["actual_gain"] / cycle["expected_delta"]) * 100)
                
                summary.append({
                    "conditions": f"{cycle['conditions'].get('weather_state', 'unknown')}, "
                                f"wind={cycle['conditions'].get('wind_speed', 0):.0f}km/h, "
                                f"uv={cycle['conditions'].get('uv_index', 0)}",
                    "decision": cycle["decision"],
                    "expected_delta": cycle.get("expected_delta", 0),
                    "actual_gain": cycle.get("actual_gain", 0),
                    "efficiency_pct": efficiency,
                })
        return summary

    async def _async_update_cycle_history(self, current_pool_temp: float) -> None:
        """Update cycle history with actual performance data and RL feedback."""
        # Si hay un ciclo previo en el historial, calcular su ganancia real y dar feedback al RL
        if self.cycle_history and self.cycle_history[-1].get("actual_gain") is None:
            last_cycle = self.cycle_history[-1]
            actual_gain = current_pool_temp - last_cycle["t_pool_start"]
            last_cycle["actual_gain"] = round(actual_gain, 2)
            
            # Calculate reward and update RL agent
            heating_duration = last_cycle.get("heating_duration", 0)
            reward = self.rl_agent.calculate_reward(
                actual_gain=actual_gain,
                duration_minutes=heating_duration,
            )
            self.rl_agent.update(reward=reward)
            self.last_reward = reward
            
            _LOGGER.info(
                "RL Feedback: expected=%.1f°C, actual=%.1f°C, duration=%dmin, reward=%.2f",
                last_cycle.get("expected_delta", 0),
                actual_gain,
                heating_duration,
                reward,
            )

        # Añadir el ciclo actual al historial
        if self.current_cycle_data:
            self.cycle_history.append(self.current_cycle_data)
            
            # Mantener solo los últimos 10 ciclos (increased for better learning)
            if len(self.cycle_history) > 10:
                self.cycle_history = self.cycle_history[-10:]
            
            # Persist both cycle history and RL agent state
            rl_state = self.rl_agent.to_dict()
            new_data = {
                **self.entry.data,
                CONF_CYCLE_HISTORY: self.cycle_history,
                CONF_Q_TABLE: rl_state["q_table"],
                CONF_RL_EPISODE_COUNT: rl_state["episode_count"],
            }
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            
            self.current_cycle_data = None

    async def _async_set_state(self, state: str, reasoning: str) -> None:
        """Update the coordinator state and reasoning."""
        self.state = state
        # Truncate reasoning to 255 chars (text entity limit)
        self.reasoning = reasoning[:252] + "..." if len(reasoning) > 255 else reasoning
        await self.async_refresh()

    async def _async_stop_heating(self, _now: datetime | None = None) -> None:
        """Stop heating cycle after duration expires."""
        _LOGGER.info("Duración de calentamiento completada, apagando bomba")
        await self._async_set_state(STATE_IDLE, self.explanation_engine.get_status_message("heating_complete"))
        await self._async_control_pump(False)
        self._heating_timer = None

    async def _async_control_pump(self, turn_on: bool) -> None:
        """Control the pool pump with shared-pump protection."""
        pump_entity = self.entry.data.get(CONF_PUMP_ENTITY_ID)
        
        if not pump_entity:
            _LOGGER.error("Pump entity ID not configured!")
            return

        # Get current physical state of the pump
        current_state = self.hass.states.get(pump_entity)
        is_already_on = current_state is not None and current_state.state == STATE_ON
            
        if turn_on:
            if is_already_on:
                # Si ya éramos los dueños, mantenemos la propiedad.
                # Solo si NO éramos los dueños y ya está prendida, asumimos que es un proceso externo (filtrado).
                if not self._pump_started_by_us:
                    _LOGGER.debug("Bomba %s ya estaba encendida, SolarPool la usará sin tomar propiedad", pump_entity)
            else:
                _LOGGER.info("Encendiendo bomba %s (Iniciado por SolarPool)", pump_entity)
                await self.hass.services.async_call("switch", SERVICE_TURN_ON, {"entity_id": pump_entity}, blocking=True)
                self._pump_started_by_us = True
                self._last_pump_on_time = utcnow()
        else:
            # Logic for turn OFF
            if not is_already_on:
                _LOGGER.debug("Pump %s is already OFF, nothing to do", pump_entity)
                self._pump_started_by_us = False
                self._last_pump_on_time = None
                return

            if self._pump_started_by_us:
                _LOGGER.info("Turning OFF pump %s (was started by SolarPool)", pump_entity)
                await self.hass.services.async_call("switch", SERVICE_TURN_OFF, {"entity_id": pump_entity}, blocking=True)
                self._pump_started_by_us = False
                self._last_pump_on_time = None
            else:
                _LOGGER.info("SolarPool cycle ended but pump %s was not started by us (filtering?). Keeping it ON.", pump_entity)
                # We reset our tracking just in case
                self._last_pump_on_time = None

    async def stop(self):
        """Stop the coordinator and cleanup."""
        if self._unsub_interval:
            self._unsub_interval()
        if self._heating_timer:
            self._heating_timer()  # Cancelar timer de calentamiento
        # Always turn off pump on stop for safety if we were heating
        if self.state in [STATE_SWEEPING, STATE_HEATING]:
            await self._async_control_pump(False)
