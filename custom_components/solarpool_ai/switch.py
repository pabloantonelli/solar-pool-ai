"""Switch platform for SolarPool AI integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarPoolCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([SolarPoolMasterSwitch(coordinator)])

class SolarPoolMasterSwitch(CoordinatorEntity[SolarPoolCoordinator], SwitchEntity):
    """Switch for SolarPool Master Control."""

    _attr_name = "SolarPool Master"
    _attr_icon = "mdi:pool-thermometer"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_master"
        self._is_on = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "SolarPool AI",
            "manufacturer": "Custom Integration",
            "model": "RL Swimming Pool Controller",
        }

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.coordinator.enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.coordinator.enabled = False
        # If we turn off the master switch, make sure the pump is off
        await self.coordinator._async_control_pump(False)
        self.async_write_ha_state()
