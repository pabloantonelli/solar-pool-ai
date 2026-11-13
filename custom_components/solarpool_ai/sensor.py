"""Sensor platform for SolarPool AI integration."""
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity, solarpool_device_info
from .translations import get_text


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


class SolarPoolBaseSensor(CoordinatorEntity[SolarPoolCoordinator], SensorEntity):
    """Base de los sensores originales (nombres fijos para no cambiar entity_ids existentes)."""

    def __init__(self, coordinator: SolarPoolCoordinator, key: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"SolarPool {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = solarpool_device_info(coordinator.entry.entry_id)


class SolarPoolStatusSensor(SolarPoolBaseSensor):
    """Estado actual (traducido) + detalles de la sesión."""

    _attr_icon = "mdi:pool"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "status", "Status")

    @property
    def native_value(self) -> str:
        return self.coordinator.explanation_engine.get_state_name(self.coordinator.state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            "state_code": c.state,
            "mode": c.mode,
            "session_active": c.session_active,
            "delta_on": c.delta_on,
            "delta_off": round(c.delta_off, 2),
            "last_session": c.last_session,
        }


class SolarPoolReasoningSensor(SolarPoolBaseSensor):
    """Explicación de la decisión actual."""

    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "reasoning", "Reasoning")

    @property
    def native_value(self) -> str:
        return self.coordinator.reasoning


class SolarPoolExpectedGainSensor(SolarPoolBaseSensor):
    """Ganancia esperada para una hora de calentamiento (aprendida por condiciones)."""

    _attr_icon = "mdi:thermometer-plus"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "expected_gain", "Expected Gain")

    @property
    def native_value(self) -> float:
        return self.coordinator.expected_gain


class SolarPoolNextRunSensor(SolarPoolBaseSensor):
    """Próxima evaluación automática."""

    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "next_run", "Next Run")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.next_cycle_time


class SolarPoolRLEpisodesSensor(SolarPoolBaseSensor):
    """Cantidad de sesiones aprendidas."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_episodes", "RL Episodes")

    @property
    def native_value(self) -> int:
        return self.coordinator.rl_agent.episode_count


class SolarPoolRLPhaseSensor(SolarPoolBaseSensor):
    """Fase de aprendizaje."""

    _attr_icon = "mdi:school"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_phase", "RL Phase")

    @property
    def native_value(self) -> str:
        agent = self.coordinator.rl_agent
        lang = self.coordinator.explanation_engine.language
        if agent.is_bootstrap:
            return get_text("rl_phases.bootstrap", lang)
        if agent.is_warmup:
            return get_text("rl_phases.training", lang)
        return get_text("rl_phases.production", lang)


class SolarPoolRLEpsilonSensor(SolarPoolBaseSensor):
    """Tasa de exploración."""

    _attr_icon = "mdi:chart-scatter-plot"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_epsilon", "RL Exploration Rate")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.rl_agent.exploration_rate, 3)


class SolarPoolRLRewardSensor(SolarPoolBaseSensor):
    """Recompensa de la última sesión."""

    _attr_icon = "mdi:medal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_reward", "RL Last Reward")

    @property
    def native_value(self) -> float:
        return self.coordinator.last_reward


class SolarPoolDailyGainSensor(SolarPoolBaseSensor):
    """Ganancia acumulada del día."""

    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "daily_gain", "Total Daily Gain")

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
