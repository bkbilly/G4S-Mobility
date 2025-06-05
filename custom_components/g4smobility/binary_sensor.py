"""Platform for 3DTracking binary sensor entities."""
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify as ha_slugify

from .const import (
    DOMAIN,
    BINARY_SENSOR_KEYWORD_TO_DEVICE_CLASS_MAP,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 3DTracking binary sensor platform."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []
    
    if coordinator.data:
        for unit_data in coordinator.data:
            if not (unit_data and "Uid" in unit_data and "Name" in unit_data):
                _LOGGER.warning("Skipping binary sensors for unit due to missing Uid or Name: %s", unit_data)
                continue
            
            unit_uid = unit_data["Uid"]
            vehicle_name = unit_data["Name"]

            input_outputs = unit_data.get("Position", {}).get("InputOutputs", [])
            if not input_outputs:
                continue

            # Keep track of generated unique IDs to handle potential collisions if SystemName + Description isn't unique enough
            # (though it usually should be)
            generated_unique_suffixes_for_unit = set()

            for index, io_item in enumerate(input_outputs):
                system_name = io_item.get("SystemName")
                description = io_item.get("Description", "")
                user_description = io_item.get("UserDescription", "")
                
                if not system_name:
                    _LOGGER.debug("Skipping IO item without SystemName at index %d for unit %s: %s", index, unit_uid, io_item)
                    continue

                # Determine the display name for the sensor
                # Prioritize UserDescription, then Description, then SystemName
                io_display_name = user_description.strip()
                if not io_display_name:
                    io_display_name = description.strip()
                if not io_display_name:
                    io_display_name = system_name # Fallback to system name if others are empty

                # Create a unique key part for the ID based on system_name and the chosen display name
                # This aims to make IDs distinct for each IO entry.
                unique_key_part_base = f"{ha_slugify(system_name)}_{ha_slugify(io_display_name)}"
                unique_key_part = unique_key_part_base
                
                # Handle cases where SystemName + DisplayName might not be unique (e.g. two "Siren" under "aux10")
                # by appending an index if a collision is detected.
                # This is a simple collision avoidance for this specific case.
                # A more robust solution might involve hashing the full io_item if truly needed.
                counter = 0
                while unique_key_part in generated_unique_suffixes_for_unit:
                    counter += 1
                    unique_key_part = f"{unique_key_part_base}_{counter}"
                generated_unique_suffixes_for_unit.add(unique_key_part)
                
                initial_is_on = io_item.get("Active", False)

                entities.append(
                    ThreeDTrackingVehicleBinarySensor(
                        coordinator,
                        unit_uid,
                        vehicle_name,
                        config_entry.entry_id,
                        io_item, # Pass the full item for later reference
                        unique_key_part, # The unique part for the entity_id
                        io_display_name,
                        initial_is_on
                    )
                )
    
    async_add_entities(entities)


class ThreeDTrackingVehicleBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A 3DTracking vehicle binary sensor entity from an individual InputOutput item."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unit_uid: str,
        vehicle_name: str,
        config_entry_id: str,
        io_item_data: dict, # Store the initial IO item data for reference
        unique_io_key: str, # The unique key part derived for this specific IO
        io_display_name: str,
        initial_is_on: bool
    ):
        """Initialize the 3DTracking binary sensor."""
        super().__init__(coordinator)
        self._unit_uid = unit_uid
        # Store key fields from the io_item_data to identify it during updates
        self._io_system_name = io_item_data.get("SystemName")
        self._io_description = io_item_data.get("Description")
        self._io_user_description = io_item_data.get("UserDescription")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unit_uid)},
            name=vehicle_name,
            manufacturer="3DTracking",
            model="Vehicle",
            via_device=(DOMAIN, config_entry_id),
        )
        self._attr_name = io_display_name 
        self._attr_unique_id = f"{self._unit_uid}_io_{unique_io_key}"
        self._attr_has_entity_name = True
        self._attr_is_on = initial_is_on

        self._attr_extra_state_attributes = {
            "system_name": self._io_system_name,
            "api_description": self._io_description,
            "api_user_description": self._io_user_description,
        }

        self._attr_device_class = None
        search_name_for_class = io_display_name.lower()
        for keyword, dev_class in BINARY_SENSOR_KEYWORD_TO_DEVICE_CLASS_MAP.items():
            if keyword in search_name_for_class:
                self._attr_device_class = dev_class
                break
        
    def _find_unit_data(self, units_list: list[dict] | None) -> dict | None:
        """Find this sensor's parent unit data from the coordinator's list."""
        if not units_list:
            return None
        return next((unit for unit in units_list if unit.get("Uid") == self._unit_uid), None)

    def _find_current_io_item(self, unit_data: dict | None) -> dict | None:
        """Find the specific IO item for this entity in the latest unit_data."""
        if not unit_data:
            return None
        
        input_outputs = unit_data.get("Position", {}).get("InputOutputs", [])
        for item in input_outputs:
            # Match based on the identifying fields stored during init
            if (item.get("SystemName") == self._io_system_name and
                item.get("Description") == self._io_description and
                item.get("UserDescription") == self._io_user_description):
                return item
        return None # Item not found

    def _update_sensor_state(self, current_io_item_data: dict | None) -> None:
        """Update the binary sensor's state based on its specific IO item data."""
        if not current_io_item_data:
            # This specific IO item is no longer reported for the unit
            self._attr_is_on = None 
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_is_on = current_io_item_data.get("Active", False)
        
        # Optionally update attributes if they can change, though usually SystemName/Description are fixed
        # self._attr_extra_state_attributes["api_description"] = current_io_item_data.get("Description")
        # self._attr_extra_state_attributes["api_user_description"] = current_io_item_data.get("UserDescription")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        unit_data = self._find_unit_data(self.coordinator.data)
        current_io_item = self._find_current_io_item(unit_data)
        self._update_sensor_state(current_io_item)
        self.async_write_ha_state()