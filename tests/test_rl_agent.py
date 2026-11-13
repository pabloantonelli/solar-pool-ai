"""Tests del agente RL (sin Home Assistant)."""
from __future__ import annotations

from unittest.mock import patch

from custom_components.solarpool_ai.const import RL_ACTION_SWEEP, RL_ACTION_WAIT, RL_SWEEP_COST
from custom_components.solarpool_ai.rl_agent import RLAgent

SUNNY = {"uv_index": 8, "wind_speed": 5, "sun_elevation": 50, "solar_hour_offset": 0}
CLOUDY = {"uv_index": 1, "wind_speed": 35, "sun_elevation": 15, "solar_hour_offset": -3}


def test_state_space_and_bins() -> None:
    agent = RLAgent()
    states = {
        agent.discretize_state({"uv_index": uv, "wind_speed": w, "sun_elevation": e, "solar_hour_offset": t})
        for uv in (0, 4, 7, 11)
        for w in (0, 20, 40)
        for e in (10, 30, 60)
        for t in (-3, 0, 3)
    }
    assert states == set(range(RLAgent.NUM_STATES))


def test_bootstrap_always_sweeps() -> None:
    agent = RLAgent()
    assert agent.is_bootstrap
    for _ in range(20):
        assert agent.get_action(CLOUDY)["action"] == RL_ACTION_SWEEP


def test_update_is_attributed_to_given_state_only() -> None:
    agent = RLAgent()
    s_sunny = agent.discretize_state(SUNNY)
    s_cloudy = agent.discretize_state(CLOUDY)
    before_sunny = list(agent.q_table[s_sunny])

    agent.update(s_cloudy, RL_ACTION_SWEEP, -0.1)

    assert agent.q_table[s_sunny] == before_sunny
    assert agent.q_table[s_cloudy][RL_ACTION_SWEEP] < 0
    assert agent.episode_count == 1


def test_wait_updates_are_ignored() -> None:
    agent = RLAgent()
    agent.update(0, RL_ACTION_WAIT, 5.0)
    assert agent.q_table[0][RL_ACTION_WAIT] == 0.0
    assert agent.episode_count == 0


def test_learns_to_wait_in_bad_conditions_and_sweep_in_good() -> None:
    agent = RLAgent(episode_count=0)
    s_cloudy = agent.discretize_state(CLOUDY)
    s_sunny = agent.discretize_state(SUNNY)
    for _ in range(30):
        agent.update(s_cloudy, RL_ACTION_SWEEP, agent.calculate_reward(False, 0, 3))
        agent.update(s_sunny, RL_ACTION_SWEEP, agent.calculate_reward(True, 0.8, 60))
    assert not agent.is_warmup
    with patch("custom_components.solarpool_ai.rl_agent.random.random", return_value=0.99):
        assert agent.get_action(CLOUDY)["action"] == RL_ACTION_WAIT
        assert agent.get_action(SUNNY)["action"] == RL_ACTION_SWEEP
    # Exploración ocasional en estados "malos"
    with patch("custom_components.solarpool_ai.rl_agent.random.random", return_value=0.0):
        result = agent.get_action(CLOUDY)
        assert result["action"] == RL_ACTION_SWEEP and result["is_learning"]


def test_rewards() -> None:
    assert RLAgent.calculate_reward(False, 0.0, 3) == -RL_SWEEP_COST
    assert RLAgent.calculate_reward(True, 1.0, 60) == 0.95
    assert RLAgent.calculate_reward(True, -0.2, 60) < 0


def test_gain_rate_learning() -> None:
    agent = RLAgent()
    s = agent.discretize_state(SUNNY)
    heuristic = agent.expected_gain(SUNNY, 60)
    assert heuristic == 0.8
    agent.update_gain_rate(s, 1.5)
    assert agent.expected_gain(SUNNY, 60) == 1.5
    agent.update_gain_rate(s, 0.5)
    assert agent.expected_gain(SUNNY, 60) == 1.2  # EMA alpha 0.3
    assert agent.expected_gain(SUNNY, 30) == 0.6


def test_serialization_roundtrip_and_legacy_reset() -> None:
    agent = RLAgent()
    agent.update(3, RL_ACTION_SWEEP, 0.7)
    agent.update_gain_rate(3, 0.9)
    restored = RLAgent.from_dict(agent.to_dict())
    assert restored.q_table == agent.q_table
    assert restored.counts == agent.counts
    assert restored.gain_rate == agent.gain_rate
    assert restored.episode_count == 1

    # Formato viejo (Q-table 144x5, sin versión) → se descarta
    legacy = {"q_table": [[0.0] * 5 for _ in range(144)], "episode_count": 80}
    assert RLAgent.from_dict(legacy).episode_count == 0
    assert RLAgent(q_table=legacy["q_table"], episode_count=80).episode_count == 0
