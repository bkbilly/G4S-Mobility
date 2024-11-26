import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from .const import (
    DOMAIN,
    PLATFORMS,
)

from .g4smobility import G4SMobility


LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    g4smobility = await hass.async_add_executor_job(G4SMobility, entry.data["username"], entry.data["password"])
    hass.data[DOMAIN][entry.entry_id] = g4smobility

    coordinator = G4SMobilityDataUpdateCoordinator(hass, g4smobility, int(entry.data["polling"]))
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_connect_or_timeout(hass, g4smobility):
    userId = None
    try:
        userId = g4smobility.options.get("user")
        if userId != None or "":
            LOGGER.info("Success Connecting to G4S Mobility")
    except Exception as err:
        LOGGER.error("Error connecting to G4S Mobility")
        raise CannotConnect from err


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class G4SMobilityDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the refresh of the g4smobility data api"""

    def __init__(self, hass, g4smobility, pollingRate):
        self._g4smobility = g4smobility
        self._hass = hass
        self._pollingRate = int(pollingRate)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=pollingRate),
        )

    @property
    def g4smobility(self):
        return self._g4smobility

    @property
    def pollingRate(self):
        return self._pollingRate

    async def _async_update_data(self):
        """Update data via library."""
        try:
            await self._hass.async_add_executor_job(self.g4smobility.update)
        except Exception as error:
            LOGGER.error("Error updating G4S Mobility data\n{error}")
            raise UpdateFailed(error) from error
        return self.g4smobility
