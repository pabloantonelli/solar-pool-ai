"""Explanation templates engine for SolarPool AI.

Genera textos legibles (multi-idioma) para las decisiones del sistema.
Los textos viven en messages/<idioma>.json bajo la clave `solarpool`.
"""
from __future__ import annotations

from typing import Any

from .translations import get_template, get_text


class ExplanationEngine:
    """Engine for generating human-readable explanations."""

    def __init__(self, language: str = "es") -> None:
        """Initialize the explanation engine."""
        self.language = language

    def get_heating_explanation(self, context: dict[str, Any]) -> str:
        """Explicación al empezar a calentar (ΔT tras el barrido >= delta_on)."""
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        uv = context.get("uv_index") or 0
        wind = context.get("wind_speed") or 0
        if uv >= 6 and wind < 15 and delta >= 4:
            return get_template("on_optimal", self.language)
        return get_template("on_marginal", self.language)

    def get_off_explanation(self, context: dict[str, Any], delta_on: float) -> str:
        """Explicación cuando el barrido no alcanzó el ΔT mínimo."""
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        wind = context.get("wind_speed") or 0
        uv = context.get("uv_index") or 0
        elevation = context.get("sun_elevation") or 0
        weather = context.get("weather_state", "")

        if elevation < 10:
            return get_template("off_low_sun", self.language, elevation=elevation)
        if wind > 25:
            return get_template("off_wind", self.language, wind=wind)
        if uv < 3:
            return get_template("off_low_uv", self.language, uv=uv)
        if weather in ["cloudy", "rainy", "pouring", "fog"]:
            return get_template("off_clouds", self.language)
        return get_template("off_delta", self.language, delta=delta, delta_on=delta_on)

    def get_wait_explanation(self, context: dict[str, Any], expected_gain: float) -> str:
        """Explicación cuando el agente decide no barrer este ciclo."""
        return get_template(
            "wait",
            self.language,
            uv=context.get("uv_index") or 0,
            wind=context.get("wind_speed") or 0,
            gain=expected_gain,
        )

    def get_sweep_message(self, forced: bool, is_learning: bool, is_bootstrap: bool) -> str:
        """Mensaje al iniciar un barrido."""
        if forced:
            return self.get_status_message("sweep_forced")
        if is_bootstrap:
            return get_template("warmup", self.language)
        if is_learning:
            return get_template("on_learning", self.language)
        return self.get_status_message("sweep_starting")

    def get_status_message(self, key: str, **kwargs: Any) -> str:
        """Mensaje de estado traducido (status_messages.<key>)."""
        return get_text(f"status_messages.{key}", self.language, **kwargs)

    def get_problem_text(self, key: str) -> str:
        """Descripción traducida de un problema (problems.<key>)."""
        return get_text(f"problems.{key}", self.language)

    def get_state_name(self, state: str) -> str:
        """Nombre traducido de un estado."""
        return get_text(f"states.{state}", self.language)
