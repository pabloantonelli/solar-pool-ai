"""Number platform for SolarPool AI - parámetros configurables (guardados en entry.options)."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DELTA_OFF,
    CONF_DELTA_ON,
    CONF_FROST_THRESHOLD,
    CONF_MAX_TEMP,
    CONF_SWEEP_DURATION,
    DEFAULT_DELTA_OFF,
    DEFAULT_DELTA_ON,
    DEFAULT_FROST_THRESHOLD,
    DEFAULT_MAX_TEMP,
    DEFAULT_SWEEP_DURATION,
    DOMAIN,
)
from .coordinator import SolarPoolCoordinator
from .entity import solarpool_device_info

_LOGGER = logging.getLogger(__name__)

# key, default, min, max, step, unit, icon (nombre traducido vía translation_key = key)
NUMBERS: tuple[tuple, ...] = (
    (CONF_MAX_TEMP, DEFAULT_MAX_TEMP, 20.0, 40.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:thermometer-high"),
    (CONF_SWEEP_DURATION, DEFAULT_SWEEP_DURATION, 60, 600, 30, "s", "mdi:timer-sand"),
    (CONF_DELTA_ON, DEFAULT_DELTA_ON, 0.5, 6.0, 0.1, UnitOfTemperature.CELSIUS, "mdi:thermometer-chevron-up"),
    (CONF_DELTA_OFF, DEFAULT_DELTA_OFF, 0.2, 4.0, 0.1, UnitOfTemperature.CELSIUS, "mdi:thermometer-chevron-down"),
    (CONF_FROST_THRESHOLD, DEFAULT_FROST_THRESHOLD, -5.0, 8.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:snowflake-thermometer"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SolarPoolNumber(coordinator, *spec) for spec in NUMBERS)


class SolarPoolNumber(NumberEntity):
    """Parámetro guardado en entry.options (el coordinator lo lee con _conf)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SolarPoolCoordinator,
        key: str,
        default: float,
        min_value: float,
        max_value: float,
        step: float,
        unit: str,
        icon: str,
    ) -> None:
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.entry = coordinator.entry
        self._key = key
        self._default = default
        self._attr_unique_id = f"{self.entry.entry_id}_{key}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_translation_key = key
        self._attr_device_info = solarpool_device_info(self.entry.entry_id)

    @property
    def native_value(self) -> float:
        return float(self.coordinator._conf(self._key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        """Guarda en options; el coordinator lo lee con _conf en cada uso."""
        self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, self._key: value})
        self.async_write_ha_state()
        _LOGGER.info("SolarPool %s actualizado a %s", self._key, value)
