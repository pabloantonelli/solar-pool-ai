"""The SolarPool AI integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SCAN_INTERVAL, DOMAIN, LEGACY_DATA_KEYS
from .coordinator import SolarPoolCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migra entradas viejas.

    1.1 → 1.2: el estado RL/historial ya no vive en entry.data (pasa a un Store propio).
    El formato del agente cambió en v0.1.0, así que los datos viejos se descartan.
    """
    if entry.version == 1 and entry.minor_version < 2:
        new_data = {k: v for k, v in entry.data.items() if k not in LEGACY_DATA_KEYS}
        removed = sorted(set(entry.data) - set(new_data))
        hass.config_entries.async_update_entry(entry, data=new_data, minor_version=2)
        _LOGGER.info("SolarPool AI migrado a 1.2 (claves legacy eliminadas: %s)", removed)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SolarPool AI from a config entry."""
    _async_remove_obsolete_entities(hass, entry)
    coordinator = SolarPoolCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


def _async_remove_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Borra del registro entidades que ya no existen (p. ej. el intervalo, fijo desde v0.2.0)."""
    registry = er.async_get(hass)
    for platform, key in (("number", CONF_SCAN_INTERVAL),):
        entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
        if entity_id:
            registry.async_remove(entity_id)
            _LOGGER.info("SolarPool AI: entidad obsoleta eliminada: %s", entity_id)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Aplica cambios de options (idioma) sin recargar."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_options_updated()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SolarPoolCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok
