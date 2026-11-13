"""Tests de integración del coordinator (máquina de estados real con HA de prueba)."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.solarpool_ai.const import (
    CONF_FROST_PROTECTION,
    CONF_MAX_TEMP,
    CONF_NIGHT_COOLING,
    DOMAIN,
    MODE_BOOST,
    MODE_VACATION,
    PROBLEM_POOL_SENSOR,
    STATE_COOLDOWN,
    STATE_COOLING,
    STATE_FROST,
    STATE_HEATING,
    STATE_IDLE,
    STATE_SWEEPING,
    STATE_WAITING,
)

from .conftest import (
    POOL,
    PUMP,
    RETURN,
    coordinator_of,
    set_day,
    set_night,
    set_world,
    setup_entry,
)


async def _start_and_sweep(hass: HomeAssistant, advance, ret_after_sweep: float):
    """Arranca la integración, deja correr el primer ciclo y completa el barrido."""
    entry = await setup_entry(hass)
    coord = coordinator_of(hass, entry)
    await advance(15)  # primer ciclo (10 s después de cargar)
    assert coord.state == STATE_SWEEPING
    hass.states.async_set(RETURN, str(ret_after_sweep))
    await advance(75)  # 3 lecturas estables tras >= 60 s
    return entry, coord


async def test_sweep_heat_and_stop_by_hysteresis(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25)
    entry, coord = await _start_and_sweep(hass, advance, ret_after_sweep=30)

    assert coord.state == STATE_HEATING
    assert hass.states.get(PUMP).state == "on"
    assert coord.current_delta == 5.0

    # El agua sube y el ΔT cae por debajo de delta_off (1.0)
    hass.states.async_set(POOL, "26")
    hass.states.async_set(RETURN, "26.5")
    await advance(60 * 5)
    assert coord.state == STATE_IDLE
    # Respeta el tiempo mínimo de bomba (10 min desde que se prendió)
    await advance(60 * 6)
    assert hass.states.get(PUMP).state == "off"
    assert pump_calls == ["on", "off"]

    # Hubo una sesión calentando (luego el tick de 10 min puede hacer otro barrido de bootstrap)
    session = coord.history[0]
    assert session["outcome"] == "heated"
    assert session["gain"] == 1.0
    assert session["reward"] > 0
    assert coord.rl_agent.episode_count >= 1
    assert coord.daily_gain == 1.0


async def test_low_delta_turns_off_and_penalizes_sweep(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25)
    entry, coord = await _start_and_sweep(hass, advance, ret_after_sweep=25.5)

    assert coord.state == STATE_IDLE
    assert coord.last_session["outcome"] == "low_delta"
    assert coord.last_reward < 0
    assert hass.states.get(PUMP).state == "on"  # protección de tiempo mínimo
    await advance(60 * 10)
    assert hass.states.get(PUMP).state == "off"


async def test_max_temp_from_options_is_respected(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=27, ret=35)
    entry = await setup_entry(hass, options={CONF_MAX_TEMP: 26.0})
    coord = coordinator_of(hass, entry)
    await advance(15)
    assert coord.state == STATE_COOLDOWN
    assert pump_calls == []


async def test_shared_pump_not_turned_off_and_not_learned(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25, pump="on")  # filtrado ya en marcha
    entry, coord = await _start_and_sweep(hass, advance, ret_after_sweep=25.3)
    await advance(60 * 15)
    assert hass.states.get(PUMP).state == "on"
    assert pump_calls == []
    assert coord.rl_agent.episode_count == 0


async def test_external_pump_off_releases_control(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25)
    entry, coord = await _start_and_sweep(hass, advance, ret_after_sweep=30)
    assert coord.state == STATE_HEATING

    hass.states.async_set(PUMP, "off")  # alguien la apaga a mano
    await hass.async_block_till_done()
    assert coord.state == STATE_IDLE
    assert coord.last_session["outcome"] == "aborted"
    assert not coord._pump_started_by_us
    assert coord.rl_agent.episode_count == 0


async def test_unload_cancels_timers_and_turns_pump_off(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25)
    entry, coord = await _start_and_sweep(hass, advance, ret_after_sweep=30)
    assert coord.state == STATE_HEATING

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(PUMP).state == "off"
    calls_after_unload = list(pump_calls)
    await advance(60 * 30)
    assert pump_calls == calls_after_unload


async def test_resume_heating_after_restart(hass: HomeAssistant, hass_storage, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=30, pump="on")
    now = dt_util.utcnow().isoformat()
    hass_storage[f"{DOMAIN}.test_entry"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.test_entry",
        "data": {
            "pump_owned": True,
            "session": {
                "rl_state": 0, "action": 1, "learn": True, "sweep_start": now,
                "heating_start": now, "t_pool_start": 25.0, "delta_start": 5.0,
            },
        },
    }
    entry = await setup_entry(hass)
    coord = coordinator_of(hass, entry)
    await advance(15)
    assert coord.state == STATE_HEATING
    assert coord._pump_started_by_us


async def test_owned_pump_turned_off_after_restart_at_night(hass: HomeAssistant, hass_storage, pump_calls, advance) -> None:
    set_night(hass)
    set_world(hass, pool=25, ret=25, pump="on")
    hass_storage[f"{DOMAIN}.test_entry"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.test_entry",
        "data": {"pump_owned": True, "session": None},
    }
    entry = await setup_entry(hass)
    coord = coordinator_of(hass, entry)
    await advance(15)
    assert hass.states.get(PUMP).state == "off"
    assert not coord._pump_started_by_us


async def test_migration_removes_legacy_data(hass: HomeAssistant, pump_calls) -> None:
    set_day(hass)
    set_world(hass)
    entry = await setup_entry(
        hass,
        data={"q_table": [[0.0] * 5] * 144, "rl_episode_count": 99, "cycle_history": [{"x": 1}]},
        minor_version=1,
    )
    assert entry.minor_version == 2
    assert "q_table" not in entry.data
    assert "cycle_history" not in entry.data
    assert coordinator_of(hass, entry).rl_agent.episode_count == 0


async def test_vacation_and_boost_modes(hass: HomeAssistant, pump_calls, advance) -> None:
    set_day(hass)
    set_world(hass, pool=25, ret=25)
    entry = await setup_entry(hass)
    coord = coordinator_of(hass, entry)
    await coord.async_set_mode(MODE_VACATION)
    await advance(15)
    assert coord.state == STATE_IDLE
    assert pump_calls == []

    # Agente "maduro" que aprendió a esperar en estas condiciones
    state = coord.rl_agent.discretize_state(coord._gather_context(require_temps=False))
    coord.rl_agent.episode_count = 100
    coord.rl_agent.q_table[state] = [0.0, -1.0]
    coord._last_sweep_time = dt_util.utcnow()
    with patch("custom_components.solarpool_ai.rl_agent.random.random", return_value=0.99):
        await coord.async_set_mode("auto")
        await coord.async_tick()
    assert coord.state == STATE_WAITING
    assert pump_calls == []

    await coord.async_set_mode(MODE_BOOST)
    await hass.async_block_till_done()
    assert coord.state == STATE_SWEEPING
    assert pump_calls == ["on"]


async def test_frost_protection_cycles_pump(hass: HomeAssistant, pump_calls, advance) -> None:
    set_night(hass)
    set_world(hass, ambient=0)
    entry = await setup_entry(hass, options={CONF_FROST_PROTECTION: True})
    coord = coordinator_of(hass, entry)
    await advance(60)
    assert coord.state == STATE_FROST
    assert hass.states.get(PUMP).state == "on"
    await advance(60 * 10)
    assert hass.states.get(PUMP).state == "off"  # pausa
    assert coord.state == STATE_FROST
    await advance(60 * 21)
    assert hass.states.get(PUMP).state == "on"  # siguiente circulación

    set_world(hass, ambient=5, pump="on")
    await advance(60)
    assert coord.state == STATE_IDLE
    assert hass.states.get(PUMP).state == "off"


async def test_night_cooling(hass: HomeAssistant, pump_calls, advance) -> None:
    set_night(hass)
    set_world(hass, pool=34, ambient=20)
    entry = await setup_entry(hass, options={CONF_NIGHT_COOLING: True})
    coord = coordinator_of(hass, entry)
    await advance(60)
    assert coord.state == STATE_COOLING
    assert hass.states.get(PUMP).state == "on"

    hass.states.async_set(POOL, "31.9")
    await advance(60)
    assert coord.state == STATE_IDLE
    assert hass.states.get(PUMP).state == "off"


async def test_problem_sensor_when_pool_sensor_unavailable(hass: HomeAssistant, pump_calls, advance) -> None:
    set_night(hass)
    set_world(hass)
    entry = await setup_entry(hass)
    coord = coordinator_of(hass, entry)
    hass.states.async_set(POOL, "unavailable")
    await advance(60 * 17)
    assert PROBLEM_POOL_SENSOR in coord.problems

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, "test_entry_problem")
    assert hass.states.get(entity_id).state == "on"

    hass.states.async_set(POOL, "25")
    await advance(60)
    assert not coord.problems
    assert hass.states.get(entity_id).state == "off"


async def test_entities_created(hass: HomeAssistant, pump_calls) -> None:
    set_night(hass)
    set_world(hass)
    await setup_entry(hass)
    registry = er.async_get(hass)
    ids = {e.unique_id for e in registry.entities.values() if e.platform == DOMAIN}
    for key in ("status", "reasoning", "delta_t", "problem", "mode", "master", "night_cooling",
                "frost_protection", "delta_on", "delta_off", "frost_threshold", "max_temp", "force_cycle"):
        assert f"test_entry_{key}" in ids, key
