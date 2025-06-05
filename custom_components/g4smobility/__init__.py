"""The 3DTracking integration."""
import logging
from datetime import timedelta
import asyncio

import async_timeout
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL, # Import new constant
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL, # For validation or logging if needed
)
from .api import ThreeDTrackingApiClient, ThreeDTrackingApiClientError, ThreeDTrackingAuthError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["device_tracker", "sensor", "binary_sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 3DTracking from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Get scan interval from options, fallback to default
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.debug("Using scan interval of %s seconds", scan_interval)


    session = aiohttp.ClientSession()
    client = ThreeDTrackingApiClient(session, username, password)

    try:
        await client.async_authenticate()
    except ThreeDTrackingAuthError as err:
        _LOGGER.error("Authentication failed for 3DTracking: %s", err)
        await session.close()
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except (ThreeDTrackingApiClientError, aiohttp.ClientError) as err:
        _LOGGER.error("API client error during setup for 3DTracking: %s", err)
        await session.close()
        raise ConfigEntryNotReady(f"API client error: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during 3DTracking setup")
        await session.close()
        raise ConfigEntryNotReady(f"Unexpected error during setup: {err}") from err


    async def async_update_data():
        """Fetch data from 3DTracking API."""
        try:
            async with async_timeout.timeout(30):
                return await client.async_get_latest_positions()
        except ThreeDTrackingAuthError as err:
            _LOGGER.warning("Authentication failed during update, will try re-authenticating: %s", err)
            raise UpdateFailed(f"Authentication error: {err}") from err
        except (ThreeDTrackingApiClientError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching 3DTracking data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching 3DTracking data: %s", err)
            raise UpdateFailed(f"Timeout communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error during update for 3DTracking:")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN} ({entry.data.get(CONF_USERNAME, entry.entry_id)})",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval), # Use the configured scan_interval
    )

    await coordinator.async_config_entry_first_refresh()
    if coordinator.data is None:
        await session.close()
        raise ConfigEntryNotReady("Initial data fetch failed for 3DTracking. Check logs for details.")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    # Add an options update listener
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading 3DTracking integration for entry %s", entry.entry_id)
    # A simple way to apply options is to reload the integration.
    # More complex scenarios might update the coordinator's interval directly.
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: ThreeDTrackingApiClient = data["client"]
        await client._session.close()
        # The update listener is automatically removed by entry.async_on_unload

    return unload_ok