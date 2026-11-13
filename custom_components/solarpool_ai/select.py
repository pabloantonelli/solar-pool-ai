"""Select platform for SolarPool AI (modo de operación)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODES
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SolarPoolModeSelect(coordinator)])


class SolarPoolModeSelect(SolarPoolEntity, SelectEntity):
    """Modo: auto / boost / vacaciones. El modo se persiste en el Store del coordinator."""

    _attr_icon = "mdi:tune-variant"
    _attr_options = list(MODES)

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        super().__init__(coordinator, "mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option)
