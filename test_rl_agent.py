#!/usr/bin/env python3
"""Test script for RL Agent and Explanation Templates.

This is a standalone test that doesn't require Home Assistant.
Run from project root:
    python3 test_rl_agent.py
"""
import sys
import os
import random

# ===== INLINE COPY OF REQUIRED CONSTANTS =====
RL_ACTIONS = [0, 20, 40, 60, 90]
DEFAULT_RL_WARMUP_EPISODES = 50
DEFAULT_RL_EXPLORATION_RATE = 0.3
DEFAULT_RL_MIN_EXPLORATION = 0.05

# ===== INLINE COPY OF TRANSLATIONS =====
TRANSLATIONS = {
    "es": {
        "states": {"idle": "Inactivo", "heating": "Calentando"},
        "status_messages": {"measuring_sensors": "Tomando medidas de sensores..."},
        "templates": {
            "on_optimal": ["☀️ Sol fuerte y viento calmo. ¡Aprovechamos!"],
            "off_wind": ["💨 Viento de {wind:.0f}km/h enfría los colectores."],
        },
    },
    "en": {
        "states": {"idle": "Idle", "heating": "Heating"},
        "status_messages": {"measuring_sensors": "Taking sensor measurements..."},
        "templates": {
            "on_optimal": ["☀️ Strong sun, calm wind. Let's heat!"],
            "off_wind": ["💨 {wind:.0f}km/h wind cools the collectors."],
        },
    },
}

def get_text(key, language="es", **kwargs):
    parts = key.split(".")
    value = TRANSLATIONS.get(language, TRANSLATIONS["es"])
    for part in parts:
        value = value.get(part, key) if isinstance(value, dict) else key
    return value.format(**kwargs) if isinstance(value, str) and kwargs else value

def get_template(category, language="es", **kwargs):
    templates = TRANSLATIONS.get(language, TRANSLATIONS["es"]).get("templates", {})
    template = random.choice(templates.get(category, [f"[{category}]"]))
    return template.format(**kwargs) if kwargs else template

# ===== INLINE COPY OF RL AGENT (simplified for testing) =====
import numpy as np

class RLAgent:
    DELTA_BINS = [0, 2, 4, 6, float('inf')]
    UV_BINS = [0, 3, 6, 9, float('inf')]
    WIND_BINS = [0, 15, 30, float('inf')]
    ELEVATION_BINS = [0, 20, 45, float('inf')]
    ALPHA = 0.1
    GAMMA = 0.9
    
    def __init__(self, q_table=None, episode_count=0):
        self.num_states = 4 * 4 * 3 * 3
        self.num_actions = len(RL_ACTIONS)
        self.q_table = np.array(q_table) if q_table else np.random.uniform(0, 0.01, (self.num_states, self.num_actions))
        self.episode_count = episode_count
        self.last_state = None
        self.last_action = None
    
    @property
    def is_warmup(self):
        return self.episode_count < DEFAULT_RL_WARMUP_EPISODES
    
    @property
    def exploration_rate(self):
        if self.episode_count < 10:
            return 1.0
        elif self.episode_count < DEFAULT_RL_WARMUP_EPISODES:
            progress = (self.episode_count - 10) / (DEFAULT_RL_WARMUP_EPISODES - 10)
            return DEFAULT_RL_EXPLORATION_RATE * (1 - progress) + DEFAULT_RL_MIN_EXPLORATION * progress
        return DEFAULT_RL_MIN_EXPLORATION
    
    def _bin_value(self, value, bins):
        for i, threshold in enumerate(bins[1:]):
            if value < threshold:
                return i
        return len(bins) - 2
    
    def discretize_state(self, context):
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        state = (self._bin_value(delta, self.DELTA_BINS) * 36 +
                 self._bin_value(context.get("uv_index", 0), self.UV_BINS) * 9 +
                 self._bin_value(context.get("wind_speed", 0), self.WIND_BINS) * 3 +
                 self._bin_value(context.get("sun_elevation", 0), self.ELEVATION_BINS))
        return min(state, self.num_states - 1)
    
    def _get_warmup_action(self, context):
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        uv = context.get("uv_index", 0)
        wind = context.get("wind_speed", 0)
        if delta < 4.0 or uv < 5 or wind > 25:
            return 0, False
        if delta > 6 and uv > 7 and wind < 15:
            return 4, False
        elif delta > 5 and uv > 6:
            return 3, False
        return 2, False
    
    def get_action(self, context):
        state = self.discretize_state(context)
        self.last_state = state
        
        if self.is_warmup and self.episode_count < 10:
            action, is_learning = self._get_warmup_action(context)
        elif random.random() < self.exploration_rate:
            action, is_learning = random.randint(0, self.num_actions - 1), True
        else:
            action, is_learning = int(np.argmax(self.q_table[state])), False
        
        self.last_action = action
        return {
            "action": "OFF" if action == 0 else "ON",
            "heating_duration_minutes": RL_ACTIONS[action],
            "expected_gain": 1.0,
            "is_learning": is_learning,
            "is_warmup": self.is_warmup,
        }
    
    def calculate_reward(self, actual_gain, duration_minutes, pump_cost_per_hour=0.5):
        if duration_minutes == 0:
            return 0.1 if actual_gain < 0.5 else -0.5
        hours = duration_minutes / 60
        return round(actual_gain - pump_cost_per_hour * hours, 2)
    
    def update(self, reward, next_context=None):
        if self.last_state is None:
            return
        max_next_q = 0 if next_context is None else np.max(self.q_table[self.discretize_state(next_context)])
        old_q = self.q_table[self.last_state, self.last_action]
        self.q_table[self.last_state, self.last_action] = old_q + self.ALPHA * (reward + self.GAMMA * max_next_q - old_q)
        self.episode_count += 1
        self.last_state = None

class ExplanationEngine:
    def __init__(self, language="es"):
        self.language = language
    
    def get_explanation(self, action, context, is_learning=False, is_warmup=False):
        if action == "ON":
            return get_template("on_optimal", self.language)
        return get_template("off_wind", self.language, wind=context.get("wind_speed", 0))
    
    def get_status_message(self, key, **kwargs):
        return get_text(f"status_messages.{key}", self.language, **kwargs)
    
    def get_state_name(self, state):
        return get_text(f"states.{state}", self.language)

# Test scenarios (same as test_prompt.py)
SCENARIOS = [
    {
        "name": "Delta Ineficiente (<2.0)",
        "context": {
            "t_pool": 25.0,
            "t_return": 26.5,  # delta = 1.5
            "weather_state": "sunny",
            "temperature_ext": 28.0,
            "wind_speed": 10.0,
            "uv_index": 6,
            "sun_elevation": 45.0,
        },
        "expected_action": "OFF",
    },
    {
        "name": "Viento Alto y Baja Ganancia",
        "context": {
            "t_pool": 24.0,
            "t_return": 27.0,  # delta = 3.0
            "weather_state": "partlycloudy",
            "temperature_ext": 22.0,
            "wind_speed": 35.0,
            "uv_index": 4,
            "sun_elevation": 30.0,
        },
        "expected_action": "OFF",  # warmup rules: UV < 5
    },
    {
        "name": "Condiciones Ideales",
        "context": {
            "t_pool": 25.0,
            "t_return": 33.0,  # delta = 8.0
            "weather_state": "sunny",
            "temperature_ext": 30.0,
            "wind_speed": 8.0,
            "uv_index": 9,
            "sun_elevation": 65.0,
        },
        "expected_action": "ON",
    },
    {
        "name": "Temperatura de Retorno Fría",
        "context": {
            "t_pool": 26.0,
            "t_return": 22.0,  # delta = -4.0
            "weather_state": "clear-night",
            "temperature_ext": 18.0,
            "wind_speed": 12.0,
            "uv_index": 0,
            "sun_elevation": -15.0,
        },
        "expected_action": "OFF",
    },
]


def test_rl_agent():
    """Test RL agent decisions."""
    print("\n" + "=" * 60)
    print("TEST: RL Agent Decisions (Warmup Mode)")
    print("=" * 60)
    
    agent = RLAgent()
    
    print(f"\nAgent state: episodes={agent.episode_count}, warmup={agent.is_warmup}")
    print(f"Exploration rate: {agent.exploration_rate:.2f}")
    
    for scenario in SCENARIOS:
        decision = agent.get_action(scenario["context"])
        
        action = decision["action"]
        duration = decision["heating_duration_minutes"]
        is_warmup = decision["is_warmup"]
        is_learning = decision["is_learning"]
        
        status = "✅" if action == scenario["expected_action"] else "❌"
        
        print(f"\n{status} {scenario['name']}")
        print(f"   Expected: {scenario['expected_action']}, Got: {action}")
        print(f"   Duration: {duration}min, Warmup: {is_warmup}, Learning: {is_learning}")


def test_explanation_engine():
    """Test explanation engine in both languages."""
    print("\n" + "=" * 60)
    print("TEST: Explanation Engine (ES/EN)")
    print("=" * 60)
    
    for lang in ["es", "en"]:
        print(f"\n--- Language: {lang.upper()} ---")
        engine = ExplanationEngine(lang)
        
        # Test ON optimal
        context = {"t_pool": 25, "t_return": 33, "uv_index": 9, "wind_speed": 5, "sun_elevation": 60}
        explanation = engine.get_explanation("ON", context)
        print(f"ON optimal: {explanation}")
        
        # Test OFF wind
        context = {"t_pool": 25, "t_return": 30, "uv_index": 7, "wind_speed": 30, "sun_elevation": 50}
        explanation = engine.get_explanation("OFF", context)
        print(f"OFF wind: {explanation}")
        
        # Test status messages
        status = engine.get_status_message("measuring_sensors")
        print(f"Status message: {status}")
        
        # Test state name
        state = engine.get_state_name("heating")
        print(f"State name: {state}")


def test_translations():
    """Test translation functions directly."""
    print("\n" + "=" * 60)
    print("TEST: Translation Functions")
    print("=" * 60)
    
    # Test get_text
    for lang in ["es", "en"]:
        print(f"\n--- Language: {lang.upper()} ---")
        print(f"states.heating: {get_text('states.heating', lang)}")
        print(f"states.idle: {get_text('states.idle', lang)}")
        print(f"status_messages.initializing: {get_text('status_messages.initializing', lang)}")
    
    # Test get_template
    print("\n--- Templates ---")
    for _ in range(3):
        print(f"on_optimal (ES): {get_template('on_optimal', 'es')}")


def test_discretization():
    """Test state discretization."""
    print("\n" + "=" * 60)
    print("TEST: State Discretization")
    print("=" * 60)
    
    agent = RLAgent()
    
    test_contexts = [
        {"t_pool": 25, "t_return": 26, "uv_index": 2, "wind_speed": 5, "sun_elevation": 15},   # low everything
        {"t_pool": 25, "t_return": 30, "uv_index": 5, "wind_speed": 20, "sun_elevation": 35},  # medium
        {"t_pool": 25, "t_return": 35, "uv_index": 10, "wind_speed": 5, "sun_elevation": 60},  # high everything
    ]
    
    for i, ctx in enumerate(test_contexts):
        state = agent.discretize_state(ctx)
        print(f"Context {i+1}: state_index={state}")
        print(f"    delta={ctx['t_return']-ctx['t_pool']}, uv={ctx['uv_index']}, wind={ctx['wind_speed']}, elev={ctx['sun_elevation']}")


def test_reward_calculation():
    """Test reward calculation."""
    print("\n" + "=" * 60)
    print("TEST: Reward Calculation")
    print("=" * 60)
    
    agent = RLAgent()
    
    test_cases = [
        {"actual_gain": 2.0, "duration": 60, "expected": "positive"},  # Good heating
        {"actual_gain": 0.5, "duration": 60, "expected": "negative"},  # Poor heating
        {"actual_gain": 0.0, "duration": 0, "expected": "small positive"},  # Correct OFF
        {"actual_gain": 1.5, "duration": 30, "expected": "slightly positive"},  # OK heating
    ]
    
    for case in test_cases:
        reward = agent.calculate_reward(case["actual_gain"], case["duration"])
        print(f"Gain={case['actual_gain']}°C, Duration={case['duration']}min -> Reward={reward:.2f} ({case['expected']})")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SolarPool AI - RL Agent Test Suite")
    print("=" * 60)
    
    test_translations()
    test_explanation_engine()
    test_discretization()
    test_rl_agent()
    test_reward_calculation()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60 + "\n")
