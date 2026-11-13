"""Binary sensor platform for SolarPool AI (detección de problemas)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SolarPoolProblemSensor(coordinator)])


class SolarPoolProblemSensor(SolarPoolEntity, BinarySensorEntity):
    """ON cuando hay algún problema (sensores caídos, bomba que no responde, colectores flojos)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "problem")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.problems)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        codes = sorted(self.coordinator.problems)
        engine = self.coordinator.explanation_engine
        return {"codes": codes, "reasons": [engine.get_problem_text(code) for code in codes]}
