import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    g4smobility = coordinator.data

    async_add_entities(
        G4SMobilityUnitTracker(unit_id, coordinator)
        for unit_id in g4smobility.units.keys()
    )


class G4SMobilityUnitTracker(CoordinatorEntity, TrackerEntity):
    def __init__(self, unit_id, coordinator):
        super().__init__(coordinator)
        self.unit_id = unit_id
        self.coordinator = coordinator

    @property
    def unit(self):
        return self.coordinator.data.units[self.unit_id]

    @property
    def name(self):
        return f"{self.unit["name"]} Tracker"

    @property
    def unique_id(self):
        return f"{self.unit["id"]}-tracker"

    @property
    def device_id(self):
        return self.unique_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.unit["available"]

    @property
    def latitude(self) -> float:
        return self.unit["lat"]

    @property
    def longitude(self) -> float:
        return self.unit["lon"]

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unit["id"])},
            "name": self.unit["name"],
            "manufacturer": "G4S Mobility",
        }
