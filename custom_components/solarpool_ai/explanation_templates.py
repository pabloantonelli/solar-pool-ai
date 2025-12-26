"""Explanation templates engine for SolarPool AI.

This module provides human-readable explanations for RL agent decisions,
using templates that support multiple languages.
"""
from __future__ import annotations

from typing import Any
from .translations import get_template, get_text


class ExplanationEngine:
    """Engine for generating human-readable explanations."""
    
    def __init__(self, language: str = "es") -> None:
        """Initialize the explanation engine.
        
        Args:
            language: Language code ("es" or "en")
        """
        self.language = language
    
    def set_language(self, language: str) -> None:
        """Set the language for explanations."""
        self.language = language
    
    def get_explanation(
        self,
        action: str,
        context: dict[str, Any],
        is_learning: bool = False,
        is_warmup: bool = False,
    ) -> str:
        """Generate an explanation for a decision.
        
        Args:
            action: The decision made ("ON" or "OFF")
            context: The sensor context used for the decision
            is_learning: Whether the agent is in exploration mode
            is_warmup: Whether the agent is in warmup phase
            
        Returns:
            Human-readable explanation string
        """
        delta = context.get("t_return", 0) - context.get("t_pool", 0)
        wind = context.get("wind_speed", 0)
        uv = context.get("uv_index", 0)
        elevation = context.get("sun_elevation", 0)
        weather = context.get("weather_state", "")
        
        # Warmup phase - using deterministic rules
        if is_warmup:
            return get_template("warmup", self.language)
        
        # Learning/exploration mode
        if is_learning and action == "ON":
            return get_template("on_learning", self.language)
        
        # Decision is ON
        if action == "ON":
            # Check if conditions are optimal
            if uv >= 6 and wind < 15 and delta >= 4:
                return get_template("on_optimal", self.language)
            else:
                return get_template("on_marginal", self.language)
        
        # Decision is OFF - determine the main reason
        return self._get_off_reason(delta, wind, uv, elevation, weather)
    
    def _get_off_reason(
        self,
        delta: float,
        wind: float,
        uv: float,
        elevation: float,
        weather: str,
    ) -> str:
        """Determine the main reason for an OFF decision.
        
        Prioritizes the most significant factor.
        """
        # Priority 1: Low delta T (most critical)
        if delta < 2.0:
            return get_template("off_delta", self.language, delta=delta)
        
        # Priority 2: Low sun elevation
        if elevation < 10:
            return get_template("off_low_sun", self.language, elevation=elevation)
        
        # Priority 3: High wind
        if wind > 25:
            return get_template("off_wind", self.language, wind=wind)
        
        # Priority 4: Low UV
        if uv < 3:
            return get_template("off_low_uv", self.language, uv=uv)
        
        # Priority 5: Cloudy weather
        if weather in ["cloudy", "rainy", "pouring", "fog"]:
            return get_template("off_clouds", self.language)
        
        # Default: wind (moderate but factor)
        if wind > 15:
            return get_template("off_wind", self.language, wind=wind)
        
        # Fallback
        return get_template("off_delta", self.language, delta=delta)
    
    def get_status_message(self, key: str, **kwargs) -> str:
        """Get a translated status message.
        
        Args:
            key: Status message key (e.g., "initializing", "sweep_starting")
            **kwargs: Format arguments
            
        Returns:
            Translated and formatted status message
        """
        return get_text(f"status_messages.{key}", self.language, **kwargs)
    
    def get_state_name(self, state: str) -> str:
        """Get the translated name for a state.
        
        Args:
            state: State key (e.g., "heating", "idle")
            
        Returns:
            Translated state name
        """
        return get_text(f"states.{state}", self.language)
