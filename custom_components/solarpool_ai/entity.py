"""Base entity for SolarPool AI."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarPoolCoordinator


def solarpool_device_info(entry_id: str) -> DeviceInfo:
    """Device compartido por todas las entidades de la integración."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="SolarPool AI",
        manufacturer="Custom Integration",
        model="RL Swimming Pool Controller",
    )


class SolarPoolEntity(CoordinatorEntity[SolarPoolCoordinator]):
    """Entidad base. Las entidades nuevas (v0.1.0+) usan translation_key."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPoolCoordinator, key: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = solarpool_device_info(coordinator.entry.entry_id)
