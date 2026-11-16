"""Button platform for SolarPool AI integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import logging
from .const import DOMAIN
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SolarPool AI button."""
    _LOGGER.debug("Setting up SolarPool AI button platform")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarPoolForcedCycleButton(coordinator)])

class SolarPoolForcedCycleButton(SolarPoolEntity, ButtonEntity):
    """Botón para forzar un barrido inmediato."""

    _attr_icon = "mdi:refresh-circle"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "force_cycle")

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_force_cycle()
