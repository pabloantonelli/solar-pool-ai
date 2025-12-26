"""The SolarPool AI integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_SCAN_INTERVAL
from .coordinator import SolarPoolCoordinator

_LOGGER = logging.getLogger(__name__)

# NUMBER is kept for backwards compatibility (no entities created)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SolarPool AI from a config entry."""
    coordinator = SolarPoolCoordinator(hass, entry)
    
    # Store the coordinator for platforms to use
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Initial setup of the coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Update coordinator parameters from options
    if CONF_SCAN_INTERVAL in entry.options:
        coordinator.async_update_interval(entry.options[CONF_SCAN_INTERVAL])
    
    # Reinitialize AI client if API keys or model changed
    if hasattr(coordinator, '_init_ai_client'):
        coordinator._init_ai_client()
        _LOGGER.info("AI client reinitialized after options update")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
