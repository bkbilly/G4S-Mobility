"""Platform for 3DTracking device tracker."""
import logging

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 3DTracking device tracker platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []
    if coordinator.data:
        for unit_data in coordinator.data:
            if unit_data and "Uid" in unit_data and "Name" in unit_data:
                entities.append(
                    ThreeDTrackingVehicleTracker(coordinator, unit_data, config_entry.entry_id)
                )
            else:
                _LOGGER.warning("Skipping tracker for unit due to missing Uid or Name in data: %s", unit_data)
    
    async_add_entities(entities)


class ThreeDTrackingVehicleTracker(CoordinatorEntity, TrackerEntity):
    """A 3DTracking vehicle device tracker entity."""

    _attr_has_entity_name = True # Entity name will be based on device name (e.g. "Vehicle XYZ Location")
    _attr_name = "Location" # This will make the entity name "Device Name Location"

    def __init__(self, coordinator, unit_data: dict, config_entry_id: str):
        """Initialize the 3DTracking vehicle tracker."""
        super().__init__(coordinator)
        self._unit_uid = unit_data["Uid"]
        
        self._latitude = None
        self._longitude = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unit_uid)},
            name=unit_data["Name"],
            manufacturer="3DTracking",
            model="Vehicle", # Could be enhanced if API provides vehicle type
            via_device=(DOMAIN, config_entry_id),
        )
        # Unique ID for the tracker entity.
        self._attr_unique_id = f"{self._unit_uid}_tracker"

        self._update_from_unit_data(unit_data)

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the vehicle."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the vehicle."""
        return self._longitude

    @property
    def source_type(self) -> str:
        """Return the source type, e.g. gps or router, of the device."""
        return SourceType.GPS

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        # Ignition state could be fetched here if we want dynamic icons,
        # but for simplicity, a static icon is fine.
        # ignition = self.coordinator.data ... find unit ... get ignition
        # return "mdi:car" if ignition_on else "mdi:car-off"
        return "mdi:car"

    @property
    def extra_state_attributes(self):
        """Return device specific attributes (now empty or minimal)."""
        return {} # All attributes are now sensors

    @property
    def force_update(self):
        """Force update of state when attributes change."""
        # Since attributes are moved to sensors, this might be less critical
        # but doesn't hurt to keep True for lat/lon reliability.
        return True

    def _update_from_unit_data(self, unit_data: dict):
        """Update entity state from the provided unit data."""
        device_name = self._attr_device_info["name"] if self._attr_device_info else self._unit_uid

        if unit_data and unit_data.get("Position"):
            position = unit_data["Position"]
            self._latitude = position.get("Latitude")
            self._longitude = position.get("Longitude")
            _LOGGER.debug("Tracker %s: Lat=%s, Lon=%s", device_name, self.latitude, self.longitude)
        else:
            # This case means the "Position" key is missing for this unit.
            # The entity will become unavailable if it was previously available due to lack of lat/lon.
            _LOGGER.debug("No position data for tracker %s during update. Lat/Lon will be None.", device_name)
            self._latitude = None
            self._longitude = None


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_name = self._attr_device_info["name"] if self._attr_device_info else self._unit_uid

        if self.coordinator.data is None:
            _LOGGER.debug("Coordinator data is None for tracker %s.", device_name)
            # Entity will become unavailable automatically by CoordinatorEntity logic
            # if self.available:
            #     self._latitude = None
            #     self._longitude = None
            #     self.async_write_ha_state()
            return

        unit_data = next(
            (unit for unit in self.coordinator.data if unit and unit.get("Uid") == self._unit_uid),
            None
        )

        if unit_data:
            self._update_from_unit_data(unit_data)
        else:
            _LOGGER.debug("Unit %s (%s) tracker not found in latest coordinator data.",
                            device_name, self._unit_uid)
            # Entity will become unavailable automatically if it was previously available
            # if self.available:
            #     self._latitude = None
            #     self._longitude = None
        
        self.async_write_ha_state()