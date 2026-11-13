"""Tests del config/options flow."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.solarpool_ai.const import (
    CONF_DELTA_ON,
    CONF_LANGUAGE,
    CONF_MAX_TEMP,
    CONF_SCAN_INTERVAL,
    CONF_SWEEP_DURATION,
    CONF_UV_SENSOR_ID,
)

from .conftest import set_night, set_world, setup_entry


async def test_options_flow_keeps_entity_values_and_clears_sensors(hass: HomeAssistant, pump_calls) -> None:
    set_night(hass)
    set_world(hass)
    hass.states.async_set("sensor.uv", "5")
    entry = await setup_entry(hass, options={CONF_DELTA_ON: 3.0, CONF_UV_SENSOR_ID: "sensor.uv"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "en", CONF_SWEEP_DURATION: 120, CONF_MAX_TEMP: 30, CONF_SCAN_INTERVAL: 15},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DELTA_ON] == 3.0  # escrito por la entidad number, no se pierde
    assert entry.options[CONF_UV_SENSOR_ID] is None  # borrado por el usuario

    coord = hass.data["solarpool_ai"][entry.entry_id]
    assert coord.cycle_interval_minutes == 15
    assert coord.explanation_engine.language == "en"
    assert coord.max_temp == 30
