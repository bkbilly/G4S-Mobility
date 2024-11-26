"""Platform for sensor integration."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    g4smobility = coordinator.data

    new_devices = []
    for unit in g4smobility.units.values():
        for sensor_name in unit["sensors"].keys():
            new_devices.append(G4SMobilitySensor(unit["id"], sensor_name, coordinator))
    async_add_entities(new_devices)


class G4SMobilitySensor(CoordinatorEntity, Entity):
    """Representation of a Sensor."""

    def __init__(self, unit_id, sensor_name, coordinator):
        super().__init__(coordinator)
        self._unit_id = unit_id
        self._sensor_name = sensor_name

    @property
    def unit(self):
        return self.coordinator.data.units[self._unit_id]

    @property
    def sensor(self):
        return self.unit["sensors"][self._sensor_name]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.unit["name"]} {self._sensor_name}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self.unit["id"]}-{self._sensor_name.replace(" ", "_")}"

    @property
    def device_id(self):
        return self.unique_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.unit["available"]

    @property
    def entity_category(self) -> bool:
        if self.sensor.get("type") == "diagnostic":
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._sensor_name == "Internal Battery":
            return SensorDeviceClass.BATTERY
        elif self._sensor_name == "External Battery":
            return SensorDeviceClass.VOLTAGE
        elif "humidity" in self._sensor_name.lower() and self.sensor["sign"] == "%":
            return SensorDeviceClass.HUMIDITY
        elif (" temp " in self._sensor_name.lower() or "Temperature" in self._sensor_name) and "°" in self.sensor["sign"]:
            return SensorDeviceClass.TEMPERATURE
        elif self._sensor_name == "Odometer":
            return SensorDeviceClass.DISTANCE
        elif self._sensor_name == "Speed":
            return SensorDeviceClass.SPEED
        elif self._sensor_name == "Signal Strength":
            return SensorDeviceClass.SIGNAL_STRENGTH
        elif self._sensor_name == "Last sent":
            return SensorDeviceClass.TIMESTAMP

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self.sensor["sign"]

    @property
    def icon(self):
        """Return the icon for the battery."""
        if self._sensor_name == "Satellite Count":
            return "mdi:satellite-variant"
        elif self._sensor_name == "State":
            return "mdi:car"
        elif self._sensor_name == "External Battery":
            return "mdi:car-battery"
        elif self.sensor["sign"] == "v":
            return "mdi:sine-wave"
        elif self._sensor_name == "Heading":
            return "mdi:compass-rose"
        elif "BLE " in self._sensor_name and "Battery" in self._sensor_name:
            return "mdi:battery-bluetooth-variant"
        elif self._sensor_name == "RPM":
            return "mdi:gauge-full"
        elif "fuel level" in self._sensor_name.lower():
            return "mdi:gas-station-in-use"
        return None

    @property
    def state(self):
        return self.sensor["value"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unit["id"])},
            "name": self.unit["name"],
            "manufacturer": "G4S Mobility",
        }
