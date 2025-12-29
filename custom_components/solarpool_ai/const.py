"""Constants for the SolarPool AI integration."""
from typing import Final

DOMAIN: Final = "solarpool_ai"

# Configuration keys
CONF_AI_PROVIDER: Final = "ai_provider"
CONF_API_KEY: Final = "api_key"  # Legacy - kept for backwards compat
CONF_API_KEY_GEMINI: Final = "api_key_gemini"
CONF_API_KEY_ANTHROPIC: Final = "api_key_anthropic"
CONF_MODEL_NAME: Final = "model_name"
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
CONF_CYCLE_HISTORY: Final = "cycle_history"

# AI Providers
AI_PROVIDER_GEMINI: Final = "Gemini"
AI_PROVIDER_ANTHROPIC: Final = "Anthropic"

# Defaults
DEFAULT_MODEL_GEMINI: Final = "gemini-1.5-flash"
DEFAULT_MODEL_ANTHROPIC: Final = "claude-3-haiku-20240307"
DEFAULT_SWEEP_DURATION: Final = 180
DEFAULT_MAX_TEMP: Final = 32.0
DEFAULT_SCAN_INTERVAL: Final = 10
DEFAULT_MIN_RUN_TIME: Final = 10  # Minutos mínimos de funcionamiento para proteger la bomba

# States
STATE_IDLE = "idle"
STATE_SWEEPING = "sweeping"
STATE_MEASURING = "measuring"
STATE_CONSULTING = "consulting"
STATE_HEATING = "heating"
STATE_COOLDOWN = "cooldown"
STATE_ERROR = "error"

# Language configuration
CONF_LANGUAGE: Final = "language"
SUPPORTED_LANGUAGES: Final = ["es-ar", "es-es", "en", "pt-br", "fr", "de"]
DEFAULT_LANGUAGE: Final = "es-ar"

# RL Agent configuration
CONF_Q_TABLE: Final = "q_table"
CONF_RL_EPISODE_COUNT: Final = "rl_episode_count"
DEFAULT_RL_WARMUP_EPISODES: Final = 50
DEFAULT_RL_EXPLORATION_RATE: Final = 0.3
DEFAULT_RL_MIN_EXPLORATION: Final = 0.05

# RL Actions (pump durations in minutes)
RL_ACTIONS: Final = [0, 20, 40, 60, 90]  # 0 = OFF, others = ON for X minutes

