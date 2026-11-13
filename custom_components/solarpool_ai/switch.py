"""Switch platform for SolarPool AI integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FROST_PROTECTION, CONF_NIGHT_COOLING, DOMAIN
from .coordinator import SolarPoolCoordinator
from .entity import SolarPoolEntity, solarpool_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: SolarPoolCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            SolarPoolMasterSwitch(coordinator),
            SolarPoolOptionSwitch(coordinator, CONF_NIGHT_COOLING, "mdi:snowflake-thermometer"),
            SolarPoolOptionSwitch(coordinator, CONF_FROST_PROTECTION, "mdi:snowflake-alert"),
        ]
    )


class SolarPoolMasterSwitch(CoordinatorEntity[SolarPoolCoordinator], SwitchEntity, RestoreEntity):
    """Interruptor general: apaga toda la automatización (incluidas las protecciones)."""

    _attr_name = "SolarPool Master"
    _attr_icon = "mdi:pool-thermometer"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_master"
        self._attr_device_info = solarpool_device_info(coordinator.entry.entry_id)

    async def async_added_to_hass(self) -> None:
        """Restaura el estado previo al reinicio."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self.coordinator.enabled = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_enabled(False)
        self.async_write_ha_state()


class SolarPoolOptionSwitch(SolarPoolEntity, SwitchEntity):
    """Switch de configuración guardado en entry.options (enfriamiento nocturno, antiheladas)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SolarPoolCoordinator, key: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator._conf(self._key, False))

    async def _async_set(self, value: bool) -> None:
        entry = self.coordinator.entry
        self.hass.config_entries.async_update_entry(entry, options={**entry.options, self._key: value})
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
