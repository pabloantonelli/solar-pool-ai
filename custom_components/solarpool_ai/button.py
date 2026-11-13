"""Button platform for SolarPool AI integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

import logging
from .const import DOMAIN
from .coordinator import SolarPoolCoordinator
from .entity import solarpool_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SolarPool AI button."""
    _LOGGER.debug("Setting up SolarPool AI button platform")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarPoolForcedCycleButton(coordinator)])

class SolarPoolForcedCycleButton(CoordinatorEntity[SolarPoolCoordinator], ButtonEntity):
    """Button to force a SolarPool AI cycle."""

    _attr_has_entity_name = True
    _attr_name = "Forzar consulta"
    _attr_icon = "mdi:refresh-circle"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_force_cycle"
        self._attr_device_info = solarpool_device_info(coordinator.entry.entry_id)

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_force_cycle()
