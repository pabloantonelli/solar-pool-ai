"""Sensor platform for SolarPool AI integration.

Todas las entidades usan translation_key (nombres en translations/*.json → entity.sensor).
Los unique_id se mantienen desde v0.0.x, así que los entity_id existentes no cambian.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    STATE_COOLDOWN,
    STATE_COOLING,
    STATE_ERROR,
    STATE_FROST,
    STATE_HEATING,
    STATE_IDLE,
    STATE_MEASURING,
    STATE_SWEEPING,
    STATE_WAITING,
)
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity

STATUS_OPTIONS = [
    STATE_IDLE, STATE_WAITING, STATE_SWEEPING, STATE_MEASURING, STATE_HEATING,
    STATE_COOLDOWN, STATE_COOLING, STATE_FROST, STATE_ERROR,
]
PHASE_OPTIONS = ["bootstrap", "training", "production"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            SolarPoolStatusSensor(coordinator),
            SolarPoolReasoningSensor(coordinator),
            SolarPoolExpectedGainSensor(coordinator),
            SolarPoolNextRunSensor(coordinator),
            SolarPoolRLEpisodesSensor(coordinator),
            SolarPoolRLPhaseSensor(coordinator),
            SolarPoolRLEpsilonSensor(coordinator),
            SolarPoolRLRewardSensor(coordinator),
            SolarPoolDailyGainSensor(coordinator),
            SolarPoolDeltaTSensor(coordinator),
        ]
    )


class SolarPoolStatusSensor(SolarPoolEntity, SensorEntity):
    """Estado actual (enum traducido por HA) + detalles de la sesión."""

    _attr_icon = "mdi:pool"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        return self.coordinator.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            "mode": c.mode,
            "session_active": c.session_active,
            "delta_on": c.delta_on,
            "delta_off": round(c.delta_off, 2),
            "last_session": c.last_session,
        }


class SolarPoolReasoningSensor(SolarPoolEntity, SensorEntity):
    """Explicación de la decisión actual (idioma configurado en la integración)."""

    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "reasoning")

    @property
    def native_value(self) -> str:
        return self.coordinator.reasoning


class SolarPoolExpectedGainSensor(SolarPoolEntity, SensorEntity):
    """Ganancia esperada para una hora de calentamiento (aprendida por condiciones)."""

    _attr_icon = "mdi:thermometer-plus"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "expected_gain")

    @property
    def native_value(self) -> float:
        return self.coordinator.expected_gain


class SolarPoolNextRunSensor(SolarPoolEntity, SensorEntity):
    """Próxima evaluación automática."""

    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "next_run")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.next_cycle_time


class SolarPoolDailyGainSensor(SolarPoolEntity, SensorEntity):
    """Ganancia acumulada del día."""

    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "daily_gain")

    @property
    def native_value(self) -> float:
        return self.coordinator.daily_gain


class SolarPoolDeltaTSensor(SolarPoolEntity, SensorEntity):
    """ΔT colectores (retorno - pileta) medido con la bomba en marcha."""

    _attr_icon = "mdi:delta"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "delta_t")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.current_delta


# ------------------------------------------------------------------ diagnóstico
class SolarPoolRLEpisodesSensor(SolarPoolEntity, SensorEntity):
    """Cantidad de sesiones aprendidas."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_episodes")

    @property
    def native_value(self) -> int:
        return self.coordinator.rl_agent.episode_count


class SolarPoolRLPhaseSensor(SolarPoolEntity, SensorEntity):
    """Fase de aprendizaje (enum traducido)."""

    _attr_icon = "mdi:school"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = PHASE_OPTIONS

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_phase")

    @property
    def native_value(self) -> str:
        agent = self.coordinator.rl_agent
        if agent.is_bootstrap:
            return "bootstrap"
        if agent.is_warmup:
            return "training"
        return "production"


class SolarPoolRLEpsilonSensor(SolarPoolEntity, SensorEntity):
    """Tasa de exploración."""

    _attr_icon = "mdi:chart-scatter-plot"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_epsilon")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.rl_agent.exploration_rate, 3)


class SolarPoolRLRewardSensor(SolarPoolEntity, SensorEntity):
    """Recompensa de la última sesión."""

    _attr_icon = "mdi:medal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_reward")

    @property
    def native_value(self) -> float:
        return self.coordinator.last_reward
