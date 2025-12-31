"""Switch platform for SolarPool AI integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.helpers.restore_state import RestoreEntity
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

class SolarPoolMasterSwitch(CoordinatorEntity[SolarPoolCoordinator], SwitchEntity, RestoreEntity):
    """Switch for SolarPool Master Control."""

    _attr_name = "SolarPool Master"
    _attr_icon = "mdi:pool-thermometer"

    def __init__(self, coordinator: SolarPoolCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_master"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "SolarPool AI",
            "manufacturer": "Custom Integration",
            "model": "RL Swimming Pool Controller",
        }

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self.coordinator.enabled = last_state.state == STATE_ON
            # If restored as OFF, ensure pump tracking logic is aware/pump off if needed
            if not self.coordinator.enabled:
                # We don't force pump OFF here blindly to avoid stopping it during startup if filtering,
                # but we ensure internal flag matches.
                # However, async_turn_off usually stops it. 
                # On startup, we probably just want to update the logical state.
                pass

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.coordinator.enabled = True
        self.async_write_ha_state()
        # Trigger an immediate cycle check (without forcing bypass of prerequisites)
        await self.coordinator.async_start_cycle(force=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.coordinator.enabled = False
        # If we turn off the master switch, make sure the pump is off
        await self.coordinator._async_control_pump(False)
        self.async_write_ha_state()
