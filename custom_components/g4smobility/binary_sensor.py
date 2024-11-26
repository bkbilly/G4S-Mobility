"""Platform for sensor integration."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add binary sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    g4smobility = coordinator.data

    new_devices = []
    for unit in g4smobility.units.values():
        for binary_sensor_name in unit["binary_sensors"]:
            new_devices.append(G4SMobilityBinarySensor(unit["id"], binary_sensor_name, coordinator))
    async_add_entities(new_devices)


class G4SMobilityBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    def __init__(self, unit_id, binary_sensor_name, coordinator):
        super().__init__(coordinator)
        self._unit_id = unit_id
        self._binary_sensor_name = binary_sensor_name

    @property
    def unit(self):
        return self.coordinator.data.units[self._unit_id]

    @property
    def binary_sensor(self):
        return self.unit["binary_sensors"][self._binary_sensor_name]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.unit["name"]} {self._binary_sensor_name}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self.unit["id"]}-{self._binary_sensor_name.replace(" ", "_")}"

    @property
    def device_id(self):
        return self.unique_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.unit["available"]

    @property
    def is_on(self):
        return self.binary_sensor["active"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unit["id"])},
            "name": self.unit["name"],
            "manufacturer": "G4S Mobility",
        }
