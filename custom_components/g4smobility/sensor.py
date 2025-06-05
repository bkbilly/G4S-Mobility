"""Platform for 3DTracking sensor entities."""
import logging
from typing import Any, cast
from collections.abc import Mapping

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify as ha_slugify

from .const import (
    DOMAIN,
    SENSOR_DESCRIPTIONS,
    ThreeDTrackingSensorEntityDescription,
    SENSOR_READING_TYPE_MAP,
    DEFAULT_SENSOR_READING_TYPE,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 3DTracking sensor platform."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []
    if coordinator.data:
        for unit_data in coordinator.data:
            if not (unit_data and "Uid" in unit_data and "Name" in unit_data):
                _LOGGER.warning("Skipping unit due to missing Uid or Name in data: %s", unit_data)
                continue

            vehicle_name = unit_data["Name"]
            unit_uid = unit_data["Uid"]

            for description in SENSOR_DESCRIPTIONS:
                entities.append(
                    ThreeDTrackingStaticSensor(
                        coordinator,
                        unit_uid,
                        vehicle_name,
                        config_entry.entry_id,
                        description,
                    )
                )
            
            for sensor_reading in unit_data.get("SensorReadings", []):
                if not sensor_reading.get("Name"):
                    _LOGGER.debug("Skipping sensor reading without a name for unit %s", unit_uid)
                    continue
                entities.append(
                    ThreeDTrackingDynamicSensor(
                        coordinator,
                        unit_uid,
                        vehicle_name,
                        config_entry.entry_id,
                        sensor_reading,
                    )
                )
    
    async_add_entities(entities)


def _get_value_from_path(data_dict: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    """Safely retrieve a nested value from a dictionary using a path tuple."""
    current_val = data_dict
    for key in path:
        if isinstance(current_val, dict) and key in current_val:
            current_val = current_val[key]
        else:
            return None
    return current_val


class ThreeDTrackingStaticSensor(CoordinatorEntity, SensorEntity):
    """A 3DTracking vehicle sensor entity based on a static description."""

    entity_description: ThreeDTrackingSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unit_uid: str,
        vehicle_name: str,
        config_entry_id: str,
        description: ThreeDTrackingSensorEntityDescription,
    ):
        """Initialize the 3DTracking static sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit_uid = unit_uid
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unit_uid)},
            name=vehicle_name,
            manufacturer="3DTracking",
            model="Vehicle",
            via_device=(DOMAIN, config_entry_id),
        )
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self._unit_uid}_{description.key}"
        self._attr_has_entity_name = True

        # Set native_unit_of_measurement from description if it's not a path
        if description.native_unit_of_measurement and not description.unit_path:
            self._attr_native_unit_of_measurement = description.native_unit_of_measurement

        self._update_sensor_value(self._find_unit_data(coordinator.data))

    def _find_unit_data(self, units_list: list[dict] | None) -> dict | None:
        """Find this sensor's unit data from the coordinator's list."""
        if not units_list:
            return None
        return next((unit for unit in units_list if unit.get("Uid") == self._unit_uid), None)

    def _update_sensor_value(self, unit_data: dict | None) -> None:
        """Update the sensor's state based on the unit data."""
        desc = self.entity_description
        if not unit_data:
            self._attr_native_value = None
            self._attr_available = False
            return

        if desc.availability_fn:
            self._attr_available = desc.availability_fn(unit_data)
        elif "Position" in desc.value_path:
             self._attr_available = unit_data.get("Position") is not None
        else:
            self._attr_available = True

        if not self._attr_available:
            self._attr_native_value = None
            return

        raw_value = _get_value_from_path(unit_data, desc.value_path)

        if desc.value_fn:
            self._attr_native_value = desc.value_fn(raw_value)
        else:
            self._attr_native_value = raw_value

        # Handle unit of measurement specifically for static sensors
        if desc.unit_path:
            api_unit = _get_value_from_path(unit_data, desc.unit_path)
            if api_unit:
                # Specific handling for speed units
                if desc.key == "speed" and isinstance(api_unit, str):
                    api_unit_lower = api_unit.lower()
                    if api_unit_lower == "kph":
                        self._attr_native_unit_of_measurement = "km/h"
                    elif api_unit_lower == "mph":
                        self._attr_native_unit_of_measurement = "mph"
                    else: # Use raw unit if not kph/mph, or log warning
                        self._attr_native_unit_of_measurement = api_unit
                        _LOGGER.warning(
                            "Unknown speed unit '%s' for %s. Device class 'speed' expects km/h or mph.",
                            api_unit, self.entity_id
                        )
                else: # For other sensors with unit_path
                    self._attr_native_unit_of_measurement = str(api_unit)
            else: # No unit from path, clear it if it was set by path previously
                self._attr_native_unit_of_measurement = None
        elif desc.native_unit_of_measurement and not desc.unit_path:
             # Ensure unit from description is set if no unit_path
            self._attr_native_unit_of_measurement = desc.native_unit_of_measurement


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        unit_data = self._find_unit_data(self.coordinator.data)
        self._update_sensor_value(unit_data)
        self.async_write_ha_state()


class ThreeDTrackingDynamicSensor(CoordinatorEntity, SensorEntity):
    """A 3DTracking vehicle sensor entity created dynamically from SensorReadings."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unit_uid: str,
        vehicle_name: str,
        config_entry_id: str,
        sensor_reading_data: dict,
    ):
        """Initialize the 3DTracking dynamic sensor."""
        super().__init__(coordinator)
        self._unit_uid = unit_uid
        self._sensor_reading_name = sensor_reading_data["Name"] 

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unit_uid)},
            name=vehicle_name,
            manufacturer="3DTracking",
            model="Vehicle",
            via_device=(DOMAIN, config_entry_id),
        )
        self._attr_name = self._sensor_reading_name
        self._attr_unique_id = f"{self._unit_uid}_sensor_reading_{ha_slugify(self._sensor_reading_name)}"
        self._attr_has_entity_name = True

        sensor_type_key = sensor_reading_data.get("SensorType", self._sensor_reading_name)
        sensor_type_props = SENSOR_READING_TYPE_MAP.get(sensor_type_key, {})
        
        # Fallback to Name if SensorType is not in map but Name is
        if not sensor_type_props and self._sensor_reading_name != sensor_type_key:
            sensor_type_props = SENSOR_READING_TYPE_MAP.get(self._sensor_reading_name, {})

        default_props = DEFAULT_SENSOR_READING_TYPE.copy()
        final_props = {**default_props, **sensor_type_props}

        self._attr_device_class = final_props.get("device_class")
        self._attr_state_class = final_props.get("state_class")
        if final_props.get("icon") is not None:
            self._attr_icon = final_props.get("icon") # Icon from map takes precedence
        
        # Unit of measurement from map is primary
        self._attr_native_unit_of_measurement = final_props.get("native_unit_of_measurement")
        
        _LOGGER.debug(
            "DynamicSensor %s (%s): Initial mapped unit: %s, SensorType: %s, API MeasurementSign: %s",
            self.unique_id, self._sensor_reading_name, self._attr_native_unit_of_measurement,
            sensor_reading_data.get("SensorType"), sensor_reading_data.get("MeasurementSign")
        )
        
        self._attr_extra_state_attributes = {}
        self._update_sensor_value(self._find_current_sensor_reading(coordinator.data))

    def _find_unit_data(self, units_list: list[dict] | None) -> dict | None:
        """Find this sensor's parent unit data from the coordinator's list."""
        if not units_list:
            return None
        return next((unit for unit in units_list if unit.get("Uid") == self._unit_uid), None)

    def _find_current_sensor_reading(self, units_list: list[dict] | None) -> dict | None:
        """Find current data for this specific sensor reading."""
        unit_data = self._find_unit_data(units_list)
        if unit_data:
            for reading in unit_data.get("SensorReadings", []):
                if reading.get("Name") == self._sensor_reading_name:
                    return reading
        return None

    def _update_sensor_value(self, current_reading_data: dict | None) -> None:
        """Update the sensor's state based on its specific reading data."""
        if not current_reading_data:
            self._attr_native_value = None
            self._attr_available = False
            return

        self._attr_available = True
        value_str = current_reading_data.get("Value")
        
        try:
            self._attr_native_value = float(value_str)
            if self._attr_native_value.is_integer():
                self._attr_native_value = int(self._attr_native_value)
        except (ValueError, TypeError):
            self._attr_native_value = value_str

        # If map did not provide a unit, try to use API's MeasurementSign
        if self._attr_native_unit_of_measurement is None:
            api_unit = current_reading_data.get("MeasurementSign")
            if api_unit:
                # Specific corrections for API units if needed
                if self.device_class == SensorDeviceClass.VOLTAGE and api_unit.lower() == "v":
                    self._attr_native_unit_of_measurement = "V"
                # Add other device_class specific API unit corrections here
                elif self.device_class == SensorDeviceClass.SPEED and api_unit.lower() == "kph":
                   self._attr_native_unit_of_measurement = "km/h"
                elif self.device_class == SensorDeviceClass.SPEED and api_unit.lower() == "mph":
                   self._attr_native_unit_of_measurement = "mph"
                # For TEMPERATURE, HA expects "°C", "°F", "K"
                elif self.device_class == SensorDeviceClass.TEMPERATURE and api_unit.lower() in ["c", "°c", "celsius"]:
                    self._attr_native_unit_of_measurement = "°C"
                elif self.device_class == SensorDeviceClass.TEMPERATURE and api_unit.lower() in ["f", "°f", "fahrenheit"]:
                    self._attr_native_unit_of_measurement = "°F"

                else: # Use raw API unit if no specific correction
                    self._attr_native_unit_of_measurement = api_unit
        
        self._attr_extra_state_attributes["sensor_type"] = current_reading_data.get("SensorType")
        self._attr_extra_state_attributes["reading_time_local"] = current_reading_data.get("ReadingTimeLocal")


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        current_reading_data = self._find_current_sensor_reading(self.coordinator.data)
        self._update_sensor_value(current_reading_data)
        self.async_write_ha_state()