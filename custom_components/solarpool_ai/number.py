"""Number platform for SolarPool AI - Configurable parameters."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAX_TEMP,
    CONF_SWEEP_DURATION,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_TEMP,
    DEFAULT_SWEEP_DURATION,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SolarPoolMaxTempNumber(coordinator, entry),
        SolarPoolSweepDurationNumber(coordinator, entry),
        SolarPoolScanIntervalNumber(coordinator, entry),
    ]
    
    async_add_entities(entities)


class SolarPoolNumberBase(NumberEntity):
    """Base class for SolarPool number entities."""
    
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    
    def __init__(self, coordinator, entry: ConfigEntry, key: str, default: float) -> None:
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.entry = entry
        self._key = key
        self._default = default
        self._attr_unique_id = f"{entry.entry_id}_{key}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="SolarPool AI",
            manufacturer="Custom Integration",
            model="RL Swimming Pool Controller",
        )
    
    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entry.options.get(
            self._key,
            self.entry.data.get(self._key, self._default)
        )
    
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        new_options = {**self.entry.options, self._key: value}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        
        # Notify coordinator of the change
        if hasattr(self.coordinator, 'async_update_interval') and self._key == CONF_SCAN_INTERVAL:
            self.coordinator.async_update_interval(int(value))
        
        _LOGGER.info("SolarPool %s updated to %s", self._key, value)


class SolarPoolMaxTempNumber(SolarPoolNumberBase):
    """Number entity for maximum pool temperature."""
    
    _attr_name = "Temperatura Máxima"
    _attr_icon = "mdi:thermometer-high"
    _attr_native_min_value = 20.0
    _attr_native_max_value = 40.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"
    _attr_mode = NumberMode.SLIDER
    
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, CONF_MAX_TEMP, DEFAULT_MAX_TEMP)


class SolarPoolSweepDurationNumber(SolarPoolNumberBase):
    """Number entity for sweep duration."""
    
    _attr_name = "Barrido Máximo"
    _attr_icon = "mdi:timer-sand"
    _attr_native_min_value = 60
    _attr_native_max_value = 600
    _attr_native_step = 30
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.SLIDER
    
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, CONF_SWEEP_DURATION, DEFAULT_SWEEP_DURATION)


class SolarPoolScanIntervalNumber(SolarPoolNumberBase):
    """Number entity for scan interval."""
    
    _attr_name = "Intervalo de Consulta"
    _attr_icon = "mdi:clock-outline"
    _attr_native_min_value = 5
    _attr_native_max_value = 120
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.SLIDER
    
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
