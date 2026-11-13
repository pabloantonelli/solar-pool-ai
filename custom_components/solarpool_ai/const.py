"""Constants for the SolarPool AI integration."""
from typing import Final

DOMAIN: Final = "solarpool_ai"

# ---------------------------------------------------------------------------
# Configuration keys (config entry data / options)
# ---------------------------------------------------------------------------
CONF_PUMP_ENTITY_ID: Final = "pump_entity_id"
CONF_POOL_SENSOR_ID: Final = "pool_sensor_id"
CONF_RETURN_SENSOR_ID: Final = "return_sensor_id"
CONF_WEATHER_ENTITY_ID: Final = "weather_entity_id"
# Optional sensor overrides (use specific sensors instead of weather attributes)
CONF_UV_SENSOR_ID: Final = "uv_sensor_id"
CONF_WIND_SENSOR_ID: Final = "wind_sensor_id"
CONF_AMBIENT_TEMP_SENSOR_ID: Final = "ambient_temp_sensor_id"
CONF_CLOUD_COVERAGE_SENSOR_ID: Final = "cloud_coverage_sensor_id"
CONF_SWEEP_DURATION: Final = "sweep_duration"
CONF_MAX_TEMP: Final = "max_temp"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LANGUAGE: Final = "language"
# v0.1.0: control por ΔT y protecciones (viven en entry.options)
CONF_DELTA_ON: Final = "delta_on"
CONF_DELTA_OFF: Final = "delta_off"
CONF_NIGHT_COOLING: Final = "night_cooling"
CONF_FROST_PROTECTION: Final = "frost_protection"
CONF_FROST_THRESHOLD: Final = "frost_threshold"

# Legacy keys (<= v0.0.10 guardaba el estado RL en entry.data). Se eliminan en la migración.
LEGACY_DATA_KEYS: Final = ("q_table", "rl_episode_count", "cycle_history", "api_key",
                          "api_key_gemini", "api_key_anthropic", "ai_provider", "model_name")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SWEEP_DURATION: Final = 180  # s
DEFAULT_MAX_TEMP: Final = 32.0
DEFAULT_SCAN_INTERVAL: Final = 10  # min
DEFAULT_MIN_RUN_TIME: Final = 10  # Minutos mínimos de bomba encendida (barrido + calentamiento)
DEFAULT_DELTA_ON: Final = 2.0  # ΔT mínimo tras el barrido para empezar a calentar
DEFAULT_DELTA_OFF: Final = 1.0  # ΔT por debajo del cual se corta el calentamiento (histéresis)
DEFAULT_FROST_THRESHOLD: Final = 2.0  # °C ambiente
MIN_DELTA_GAP: Final = 0.2  # delta_off siempre al menos 0.2 °C por debajo de delta_on

# ---------------------------------------------------------------------------
# Timing / control tuning
# ---------------------------------------------------------------------------
MIN_SUN_ELEVATION: Final = 5  # grados
FAST_TICK_SECONDS: Final = 60  # chequeo liviano (calentamiento, protecciones, problemas)
DELTA_OFF_CONSECUTIVE: Final = 3  # lecturas seguidas bajo delta_off para cortar
DELTA_MEDIAN_WINDOW: Final = 3
MAX_MINUTES_WITHOUT_SWEEP: Final = 60  # barrido forzado aunque el RL diga esperar
SWEEP_FIRST_CHECK_SECONDS: Final = 30
SWEEP_CHECK_SECONDS: Final = 15
SWEEP_MIN_SECONDS: Final = 60
SWEEP_STABLE_RANGE: Final = 0.2  # °C
# Enfriamiento nocturno
COOLING_MARGIN: Final = 1.0  # empezar si pileta > max_temp + margen
COOLING_AMBIENT_GAP: Final = 3.0  # y ambiente < pileta - gap
COOLING_BLOCK_MINUTES: Final = 30
# Antiheladas
FROST_ON_MINUTES: Final = 10
FROST_CYCLE_MINUTES: Final = 30
FROST_HYSTERESIS: Final = 1.0
# Detección de problemas
PROBLEM_SENSOR_UNAVAILABLE_MINUTES: Final = 15
PROBLEM_PUMP_TIMEOUT_SECONDS: Final = 30
PROBLEM_LOW_YIELD_SWEEPS: Final = 5
PROBLEM_LOW_YIELD_UV: Final = 6.0
PROBLEM_LOW_YIELD_DELTA: Final = 1.0

PROBLEM_POOL_SENSOR: Final = "pool_sensor_unavailable"
PROBLEM_RETURN_SENSOR: Final = "return_sensor_unavailable"
PROBLEM_PUMP: Final = "pump_not_responding"
PROBLEM_RETURN_STUCK: Final = "return_sensor_stuck"
PROBLEM_LOW_YIELD: Final = "collectors_low_yield"

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
STATE_IDLE: Final = "idle"
STATE_WAITING: Final = "waiting"
STATE_SWEEPING: Final = "sweeping"
STATE_MEASURING: Final = "measuring"
STATE_CONSULTING: Final = "consulting"
STATE_HEATING: Final = "heating"
STATE_COOLDOWN: Final = "cooldown"
STATE_COOLING: Final = "cooling"
STATE_FROST: Final = "frost"
STATE_ERROR: Final = "error"

# Estados en los que SolarPool está usando la bomba activamente
ACTIVE_PUMP_STATES: Final = (STATE_SWEEPING, STATE_MEASURING, STATE_HEATING, STATE_COOLING, STATE_FROST)

# ---------------------------------------------------------------------------
# Modes (select)
# ---------------------------------------------------------------------------
MODE_AUTO: Final = "auto"
MODE_BOOST: Final = "boost"
MODE_VACATION: Final = "vacation"
MODES: Final = [MODE_AUTO, MODE_BOOST, MODE_VACATION]

# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------
SUPPORTED_LANGUAGES: Final = ["es-ar", "es-es", "en", "pt-br", "fr", "de"]
DEFAULT_LANGUAGE: Final = "es-ar"

# ---------------------------------------------------------------------------
# RL agent (bandit "¿barro ahora?")
# ---------------------------------------------------------------------------
RL_ACTION_WAIT: Final = 0
RL_ACTION_SWEEP: Final = 1
RL_ACTIONS: Final = ["WAIT", "SWEEP"]
DEFAULT_RL_BOOTSTRAP_EPISODES: Final = 10  # siempre barrer
DEFAULT_RL_WARMUP_EPISODES: Final = 50
DEFAULT_RL_EXPLORATION_RATE: Final = 0.3
DEFAULT_RL_MIN_EXPLORATION: Final = 0.05
RL_PUMP_COST_PER_HOUR: Final = 0.05  # penalidad (°C equivalentes) por hora de bomba
RL_SWEEP_COST: Final = 0.1  # penalidad por barrido que no terminó calentando

# ---------------------------------------------------------------------------
# Storage / events
# ---------------------------------------------------------------------------
STORAGE_VERSION: Final = 1
HISTORY_MAX_SESSIONS: Final = 50
EVENT_SESSION_ENDED: Final = f"{DOMAIN}_session_ended"
EVENT_PROBLEM: Final = f"{DOMAIN}_problem"
