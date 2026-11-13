"""Fixtures comunes para los tests de SolarPool AI."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.solarpool_ai.const import (
    CONF_MAX_TEMP,
    CONF_POOL_SENSOR_ID,
    CONF_PUMP_ENTITY_ID,
    CONF_RETURN_SENSOR_ID,
    CONF_SCAN_INTERVAL,
    CONF_SWEEP_DURATION,
    CONF_WEATHER_ENTITY_ID,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

PUMP = "input_boolean.pool_pump"
POOL = "sensor.pool_temp"
RETURN = "sensor.return_temp"
WEATHER = "weather.home"

BASE_DATA = {
    CONF_PUMP_ENTITY_ID: PUMP,
    CONF_POOL_SENSOR_ID: POOL,
    CONF_RETURN_SENSOR_ID: RETURN,
    CONF_WEATHER_ENTITY_ID: WEATHER,
    CONF_SWEEP_DURATION: 180,
    CONF_MAX_TEMP: 32.0,
    CONF_SCAN_INTERVAL: 10,
    "language": "es-ar",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Habilita custom_components en todos los tests."""
    return


@pytest.fixture
def pump_calls(hass: HomeAssistant) -> list[str]:
    """Servicios turn_on/off que cambian el estado (input_boolean para no chocar con el componente switch real) (bomba simulada)."""
    calls: list[str] = []

    async def _on(call: ServiceCall) -> None:
        calls.append("on")
        hass.states.async_set(PUMP, "on")

    async def _off(call: ServiceCall) -> None:
        calls.append("off")
        hass.states.async_set(PUMP, "off")

    hass.services.async_register("input_boolean", "turn_on", _on)
    hass.services.async_register("input_boolean", "turn_off", _off)
    return calls


def set_day(hass: HomeAssistant, elevation: float = 50) -> None:
    """Sol alto, mediodía solar = ahora."""
    hass.states.async_set(
        "sun.sun",
        "above_horizon",
        {"elevation": elevation, "azimuth": 0, "next_noon": dt_util.utcnow().isoformat(), "rising": False},
    )


def set_night(hass: HomeAssistant) -> None:
    """Sol bajo el horizonte."""
    hass.states.async_set(
        "sun.sun",
        "below_horizon",
        {"elevation": -20, "azimuth": 0, "next_noon": (dt_util.utcnow() + timedelta(hours=12)).isoformat()},
    )


def set_world(
    hass: HomeAssistant,
    pool: float = 25.0,
    ret: float = 25.0,
    pump: str = "off",
    uv: float = 8,
    wind: float = 5,
    ambient: float = 25,
) -> None:
    """Estados iniciales de todas las entidades."""
    hass.states.async_set(PUMP, pump)
    hass.states.async_set(POOL, str(pool))
    hass.states.async_set(RETURN, str(ret))
    hass.states.async_set(
        WEATHER, "sunny", {"uv_index": uv, "wind_speed": wind, "temperature": ambient, "cloud_coverage": 0}
    )


@pytest.fixture
def advance(hass: HomeAssistant, freezer: Any) -> Callable[[float], Awaitable[None]]:
    """Avanza el reloj en pasos de 15 s disparando los timers."""

    async def _advance(seconds: float) -> None:
        remaining = seconds
        while remaining > 0:
            step = min(15, remaining)
            freezer.tick(timedelta(seconds=step))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            remaining -= step

    return _advance


async def setup_entry(
    hass: HomeAssistant, options: dict[str, Any] | None = None, data: dict[str, Any] | None = None, minor_version: int = 2
) -> MockConfigEntry:
    """Crea y carga la config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, **(data or {})},
        options=options or {},
        version=1,
        minor_version=minor_version,
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def coordinator_of(hass: HomeAssistant, entry: MockConfigEntry):
    """Coordinator de la entry."""
    return hass.data[DOMAIN][entry.entry_id]
