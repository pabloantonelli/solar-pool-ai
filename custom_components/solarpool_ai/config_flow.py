"""Config flow for SolarPool AI integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_PUMP_ENTITY_ID,
    CONF_POOL_SENSOR_ID,
    CONF_RETURN_SENSOR_ID,
    CONF_WEATHER_ENTITY_ID,
    CONF_UV_SENSOR_ID,
    CONF_WIND_SENSOR_ID,
    CONF_AMBIENT_TEMP_SENSOR_ID,
    CONF_CLOUD_COVERAGE_SENSOR_ID,
    CONF_SWEEP_DURATION,
    CONF_MAX_TEMP,
    CONF_SCAN_INTERVAL,
    CONF_LANGUAGE,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    DEFAULT_SWEEP_DURATION,
    DEFAULT_MAX_TEMP,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

class SolarPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolarPool AI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - entity mapping."""
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_parameters()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PUMP_ENTITY_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Required(CONF_POOL_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                    ),
                    vol.Required(CONF_RETURN_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                    ),
                    vol.Required(CONF_WEATHER_ENTITY_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="weather")
                    ),
                    # Optional sensor overrides
                    vol.Optional(CONF_UV_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_CLOUD_COVERAGE_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_WIND_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_AMBIENT_TEMP_SENSOR_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                    ),
                }
            ),
        )


    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the parameters step."""
        if user_input is not None:
            self._config.update(user_input)
            # Set default language if not provided
            if not self._config.get(CONF_LANGUAGE):
                self._config[CONF_LANGUAGE] = DEFAULT_LANGUAGE
            return self.async_create_entry(title="SolarPool AI", data=self._config)

        # Build language options for selector
        language_map = {
            "es-ar": "Español (Argentina)",
            "es-es": "Español (España)",
            "en": "English",
            "pt-br": "Português (Brasil)",
            "fr": "Français",
            "de": "Deutsch",
        }
        language_options = [
            {"value": lang, "label": language_map.get(lang, lang)}
            for lang in SUPPORTED_LANGUAGES
        ]

        return self.async_show_form(
            step_id="parameters",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=language_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_SWEEP_DURATION, default=DEFAULT_SWEEP_DURATION): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=60, max=600, step=1, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=20, max=40, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5, max=120, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SolarPoolOptionsFlow()


class SolarPoolOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SolarPool AI."""

    # Note: config_entry is automatically provided by Home Assistant
    # Do NOT override __init__ or try to set self.config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        try:
            # Get current values with fallback defaults
            language = self.config_entry.options.get(
                CONF_LANGUAGE,
                self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
            )
            sweep_duration = self.config_entry.options.get(
                CONF_SWEEP_DURATION,
                self.config_entry.data.get(CONF_SWEEP_DURATION, DEFAULT_SWEEP_DURATION)
            )
            max_temp = self.config_entry.options.get(
                CONF_MAX_TEMP,
                self.config_entry.data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
            )
            scan_interval = self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
            
            # Get optional sensor overrides
            uv_sensor = self.config_entry.options.get(
                CONF_UV_SENSOR_ID,
                self.config_entry.data.get(CONF_UV_SENSOR_ID)
            )
            cloud_sensor = self.config_entry.options.get(
                CONF_CLOUD_COVERAGE_SENSOR_ID,
                self.config_entry.data.get(CONF_CLOUD_COVERAGE_SENSOR_ID)
            )
            wind_sensor = self.config_entry.options.get(
                CONF_WIND_SENSOR_ID,
                self.config_entry.data.get(CONF_WIND_SENSOR_ID)
            )
            ambient_temp_sensor = self.config_entry.options.get(
                CONF_AMBIENT_TEMP_SENSOR_ID,
                self.config_entry.data.get(CONF_AMBIENT_TEMP_SENSOR_ID)
            )
            
            # Ensure values are valid
            sweep_duration = int(sweep_duration) if sweep_duration else DEFAULT_SWEEP_DURATION
            max_temp = float(max_temp) if max_temp else DEFAULT_MAX_TEMP
            scan_interval = int(scan_interval) if scan_interval else DEFAULT_SCAN_INTERVAL

            # Build language options for selector
            language_map = {
                "es-ar": "Español (Argentina)",
                "es-es": "Español (España)",
                "en": "English",
                "pt-br": "Português (Brasil)",
                "fr": "Français",
                "de": "Deutsch",
            }
            language_options = [
                {"value": lang, "label": language_map.get(lang, lang)}
                for lang in SUPPORTED_LANGUAGES
            ]
            
            # Build schema with optional sensors
            schema_dict = {
                vol.Required(
                    CONF_LANGUAGE,
                    default=language,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=language_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SWEEP_DURATION,
                    default=sweep_duration,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60, max=600, step=1, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MAX_TEMP,
                    default=max_temp,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=20, max=40, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=scan_interval,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=120, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
            
            # Add optional sensor fields
            if uv_sensor:
                schema_dict[vol.Optional(CONF_UV_SENSOR_ID, default=uv_sensor)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            else:
                schema_dict[vol.Optional(CONF_UV_SENSOR_ID)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            
            if cloud_sensor:
                schema_dict[vol.Optional(CONF_CLOUD_COVERAGE_SENSOR_ID, default=cloud_sensor)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            else:
                schema_dict[vol.Optional(CONF_CLOUD_COVERAGE_SENSOR_ID)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            
            if wind_sensor:
                schema_dict[vol.Optional(CONF_WIND_SENSOR_ID, default=wind_sensor)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            else:
                schema_dict[vol.Optional(CONF_WIND_SENSOR_ID)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            
            if ambient_temp_sensor:
                schema_dict[vol.Optional(CONF_AMBIENT_TEMP_SENSOR_ID, default=ambient_temp_sensor)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                )
            else:
                schema_dict[vol.Optional(CONF_AMBIENT_TEMP_SENSOR_ID)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                )

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(schema_dict),
            )
        except Exception as err:
            _LOGGER.error("Error loading options flow: %s", err)
            _LOGGER.error("Config entry data: %s", self.config_entry.data)
            _LOGGER.error("Config entry options: %s", self.config_entry.options)
            raise

