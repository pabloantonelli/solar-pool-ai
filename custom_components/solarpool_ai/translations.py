"""Translations and internationalization for SolarPool AI.

This module reads translations from the JSON files in the translations/ folder
following the Home Assistant standard format.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .const import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

# Cache for loaded translations
_TRANSLATIONS_CACHE: dict[str, dict[str, Any]] = {}


def _get_translations_path() -> Path:
    """Get the path to the translations directory."""
    return Path(__file__).parent / "translations"


def _load_translations(language: str) -> dict[str, Any]:
    """Load translations for a specific language from JSON file.
    
    Args:
        language: Language code (e.g., "en", "es", "pt-BR")
        
    Returns:
        Dictionary with translations
    """
    if language in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[language]
    
    translations_path = _get_translations_path()
    
    # Try exact match first
    json_file = translations_path / f"{language}.json"
    if not json_file.exists():
        # Try lowercase variant
        json_file = translations_path / f"{language.lower()}.json"
    if not json_file.exists():
        # Try base language (e.g., "es" from "es-ar")
        base_lang = language.split("-")[0]
        json_file = translations_path / f"{base_lang}.json"
    if not json_file.exists():
        # Fallback to English
        json_file = translations_path / "en.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            _TRANSLATIONS_CACHE[language] = data
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _normalize_language(language: str) -> str:
    """Normalize language code to match available translations.
    
    Args:
        language: Input language code
        
    Returns:
        Normalized language code
    """
    if language in SUPPORTED_LANGUAGES:
        return language
    
    language_lower = language.lower()
    if language_lower in SUPPORTED_LANGUAGES:
        return language_lower
    
    # Map variants to base languages
    base_lang = language.split("-")[0].lower()
    
    # Spanish variants default to es (Argentina)
    if base_lang == "es":
        return "es"
    
    # Portuguese variants
    if base_lang == "pt":
        return "pt-BR"
    
    # Check if base language exists
    if base_lang in SUPPORTED_LANGUAGES:
        return base_lang
    
    return DEFAULT_LANGUAGE


def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get a translated text string.
    
    Args:
        key: Dot-separated key path (e.g., "states.heating", "status_messages.initializing")
        language: Language code
        **kwargs: Format arguments for the string
        
    Returns:
        Translated and formatted string
    """
    language = _normalize_language(language)
    translations = _load_translations(language)
    
    # Navigate the nested dictionary
    # First try under "solarpool" namespace (our custom translations)
    parts = key.split(".")
    
    # Try solarpool namespace first
    value = translations.get("solarpool", {})
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break
    
    # If not found, try root level
    if value is None:
        value = translations
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
    
    # If still not found, return key
    if value is None:
        return key
    
    # Format with kwargs if it's a string
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    
    return str(value) if value else key


def get_template(category: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get a random template from a category.
    
    Args:
        category: Template category (e.g., "on_optimal", "off_wind")
        language: Language code
        **kwargs: Format arguments for the template
        
    Returns:
        Random template from the category, formatted with kwargs
    """
    language = _normalize_language(language)
    translations = _load_translations(language)
    
    # Get templates from solarpool namespace
    solarpool = translations.get("solarpool", {})
    templates = solarpool.get("templates", {})
    category_templates = templates.get(category, [])
    
    if not category_templates:
        return f"[{category}]"
    
    template = random.choice(category_templates)
    
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    
    return template


def clear_cache() -> None:
    """Clear the translations cache (useful for testing or hot-reload)."""
    _TRANSLATIONS_CACHE.clear()
