"""Config flow for 3DTracking integration."""
import logging
import asyncio
from typing import Any, Dict, Optional # Added Optional

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv # For vol.All

from .const import (
    DOMAIN,
    API_AUTH_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)
from .api import ThreeDTrackingApiClient, ThreeDTrackingAuthError, ThreeDTrackingApiClientError

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class ThreeDTrackingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 3DTracking."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ThreeDTrackingOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            temp_session = aiohttp.ClientSession()
            client = ThreeDTrackingApiClient(temp_session, username, password)

            try:
                await client.async_authenticate()
                await temp_session.close()

                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                # Add default scan interval to the main data initially if desired,
                # or just rely on options flow. For simplicity, we'll let options handle it.
                # user_input[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL

                return self.async_create_entry(title=f"3DTracking ({username})", data=user_input)

            except ThreeDTrackingAuthError:
                _LOGGER.warning("Invalid credentials for 3DTracking username: %s", username)
                errors["base"] = "invalid_auth"
            except (ThreeDTrackingApiClientError, aiohttp.ClientError) as err:
                _LOGGER.error("API error during 3DTracking config flow: %s", err)
                errors["base"] = "cannot_connect"
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout connecting to 3DTracking API during config flow.")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during 3DTracking config flow:")
                errors["base"] = "unknown"
            finally:
                if not temp_session.closed:
                    await temp_session.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    # _async_current_entries can be removed if not used, it was specific to an older HA version's example
    # @callback
    # def _async_current_entries(self):
    #     """Return the current entries for this flow."""
    #     # This is not standard and likely not needed.
    #     # If you need to access current entries, use self.hass.config_entries.async_entries(DOMAIN)
    #     return [] # Placeholder


class ThreeDTrackingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for 3DTracking."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage the options."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if not (MIN_SCAN_INTERVAL <= scan_interval <= MAX_SCAN_INTERVAL):
                errors["base"] = "invalid_scan_interval" # Or more specific error for CONF_SCAN_INTERVAL
                _LOGGER.error(
                    "Invalid scan interval: %s. Must be between %s and %s seconds.",
                    scan_interval,
                    MIN_SCAN_INTERVAL,
                    MAX_SCAN_INTERVAL,
                )
            else:
                # Create new options dictionary with the updated scan_interval
                new_options = self.config_entry.options.copy()
                new_options[CONF_SCAN_INTERVAL] = scan_interval
                return self.async_create_entry(title="", data=new_options)


        # Define the schema for the options form
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )