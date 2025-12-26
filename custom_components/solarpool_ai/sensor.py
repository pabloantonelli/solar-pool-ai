"""Sensor platform for SolarPool AI integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.util.dt import utcnow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarPoolCoordinator

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
        ]
    )

class SolarPoolBaseSensor(CoordinatorEntity[SolarPoolCoordinator], SensorEntity):
    """Base class for SolarPool sensors."""

    def __init__(self, coordinator: SolarPoolCoordinator, key: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"SolarPool {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "SolarPool AI",
            "manufacturer": "Custom Integration",
            "model": "RL Swimming Pool Controller",
        }

class SolarPoolStatusSensor(SolarPoolBaseSensor):
    """Sensor for SolarPool Status."""
    _attr_icon = "mdi:pool"
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "status", "Status")
    @property
    def native_value(self) -> str:
        return self.coordinator.explanation_engine.get_state_name(self.coordinator.state)

class SolarPoolReasoningSensor(SolarPoolBaseSensor):
    """Sensor for SolarPool Reasoning (formerly Text)."""
    _attr_icon = "mdi:brain"
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "reasoning", "Reasoning")
    @property
    def native_value(self) -> str:
        return self.coordinator.reasoning

class SolarPoolExpectedGainSensor(SolarPoolBaseSensor):
    """Sensor for SolarPool Expected Gain."""
    _attr_icon = "mdi:thermometer-plus"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "expected_gain", "Expected Gain")
    @property
    def native_value(self) -> float:
        return self.coordinator.expected_gain

class SolarPoolNextRunSensor(SolarPoolBaseSensor):
    """Sensor for SolarPool Next Run Time."""
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "next_run", "Next Run")
    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.next_cycle_time

class SolarPoolRLEpisodesSensor(SolarPoolBaseSensor):
    """Sensor for RL Episode Count."""
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_episodes", "RL Episodes")
    @property
    def native_value(self) -> int:
        return self.coordinator.rl_agent.episode_count
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC

class SolarPoolRLPhaseSensor(SolarPoolBaseSensor):
    """Sensor for RL Learning Phase."""
    _attr_icon = "mdi:school"
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_phase", "RL Phase")
    @property
    def native_value(self) -> str:
        count = self.coordinator.rl_agent.episode_count
        lang = self.coordinator.explanation_engine.language
        from .translations import get_text
        if count < 10:
            return get_text("rl_phases.bootstrap", lang)
        if count < 50:
            return get_text("rl_phases.training", lang)
        return get_text("rl_phases.production", lang)
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC

class SolarPoolRLEpsilonSensor(SolarPoolBaseSensor):
    """Sensor for RL Exploration Rate (Epsilon)."""
    _attr_icon = "mdi:chart-scatter-plot"
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_epsilon", "RL Exploration Rate")
    @property
    def native_value(self) -> float:
        return round(self.coordinator.rl_agent.exploration_rate, 3)
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC

class SolarPoolRLRewardSensor(SolarPoolBaseSensor):
    """Sensor for RL Last Reward."""
    _attr_icon = "mdi:medal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "rl_reward", "RL Last Reward")
    @property
    def native_value(self) -> float:
        return self.coordinator.last_reward
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
