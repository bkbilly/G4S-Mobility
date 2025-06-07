"""Constants for the 3DTracking integration."""
from typing import Final, Any
from dataclasses import dataclass, field
from collections.abc import Callable
from datetime import datetime, timezone
import re

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import PERCENTAGE

DOMAIN: Final = "g4smobility"

# Configuration keys
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_SCAN_INTERVAL: Final = "scan_interval" # New constant for scan interval

# Data update interval (seconds)
DEFAULT_SCAN_INTERVAL: Final = 60 # Poll every 60 seconds
MIN_SCAN_INTERVAL: Final = 10 # Minimum allowed scan interval
MAX_SCAN_INTERVAL: Final = 3600 # Maximum allowed scan interval (1 hour)


# API Endpoints
API_BASE_URL: Final = "https://api.3dtracking.net/api/v1.0"
API_AUTH_URL: Final = f"{API_BASE_URL}/Authentication/UserAuthenticate"
API_POSITIONS_URL: Final = f"{API_BASE_URL}/Units/LatestPositionsList"

def parse_api_datetime(datetime_str: str | None) -> datetime | None:
    """Parse datetime strings from the API, assuming UTC if no timezone."""
    if not datetime_str:
        return None
    try:
        dt_obj = datetime.fromisoformat(datetime_str)
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj.astimezone(timezone.utc)
    except ValueError:
        try:
            dt_obj = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
            return dt_obj.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


@dataclass(kw_only=True, frozen=True)
class ThreeDTrackingSensorEntityDescription(SensorEntityDescription):
    """Describes a 3DTracking sensor entity."""
    value_path: tuple[str, ...]
    value_fn: Callable[[Any], Any] | None = None
    unit_path: tuple[str, ...] | None = None
    availability_fn: Callable[[dict], bool] | None = None


SENSOR_DESCRIPTIONS: tuple[ThreeDTrackingSensorEntityDescription, ...] = (
    ThreeDTrackingSensorEntityDescription(
        key="speed",
        name="Speed",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_path=("Position", "Speed"),
        unit_path=("Position", "SpeedMeasure"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="heading",
        name="Heading",
        icon="mdi:compass-outline",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        value_path=("Position", "Heading"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="address",
        name="Address",
        icon="mdi:map-marker-outline",
        value_path=("Position", "Address"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="ignition_status_text",
        name="Ignition Status",
        icon="mdi:key-variant",
        value_path=("Position", "Ignition"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="odometer",
        name="Odometer",
        icon="mdi:counter",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_path=("Position", "Odometer"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="engine_status_text",
        name="Engine Status",
        icon="mdi:engine",
        value_path=("Position", "EngineStatus"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="last_gps_time_utc",
        name="Last GPS Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("Position", "GPSTimeUtc"),
        value_fn=parse_api_datetime,
        availability_fn=lambda data: data.get("Position") is not None,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="last_reported_time_utc",
        name="Last Reported Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("LastReportedTimeUTC",),
        value_fn=parse_api_datetime,
    ),
    ThreeDTrackingSensorEntityDescription(
        key="imei",
        name="IMEI",
        icon="mdi:barcode-scan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("Imei",),
    ),
    ThreeDTrackingSensorEntityDescription(
        key="engine_time",
        name="Engine Time",
        icon="mdi:engine-outline",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_path=("Position", "EngineTime"),
        availability_fn=lambda data: data.get("Position") is not None,
    ),
)

def slugify(text: str) -> str:
    """Convert a string to a slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_{2,}", "_", text)
    text = text.strip("_")
    return text if text else "unknown"

SENSOR_READING_TYPE_MAP: dict[str, dict[str, Any]] = {
    "Satellite Count": {
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:satellite-variant",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "GSM Signal Strength": {
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "External Battery": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit_of_measurement": "V",
        "icon": "mdi:car-battery",
    },
    "Battery": { # For internal battery percentage
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit_of_measurement": PERCENTAGE,
    },
    "Temp": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit_of_measurement": "°C",
    },
    "Voltage (Generic)": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit_of_measurement": "V", # ASSUMPTION: Confirm from API's MeasurementSign
    },
    "Humidity": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "native_unit_of_measurement": "%",
    },
}
DEFAULT_SENSOR_READING_TYPE: dict[str, Any] = {
    "device_class": None,
    "state_class": SensorStateClass.MEASUREMENT,
}

BINARY_SENSOR_KEYWORD_TO_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "door": BinarySensorDeviceClass.DOOR,
    "window": BinarySensorDeviceClass.WINDOW,
    "motion": BinarySensorDeviceClass.MOTION,
    "movement": BinarySensorDeviceClass.MOTION,
    "alarm": BinarySensorDeviceClass.SAFETY,
    "safety": BinarySensorDeviceClass.SAFETY,
    "ignition": BinarySensorDeviceClass.POWER,
    "power": BinarySensorDeviceClass.POWER,
    "siren": BinarySensorDeviceClass.SOUND,
    "towing": BinarySensorDeviceClass.TAMPER,
    "tamper": BinarySensorDeviceClass.TAMPER,
    "vibration": BinarySensorDeviceClass.VIBRATION,
    "lock": BinarySensorDeviceClass.LOCK,
    "light": BinarySensorDeviceClass.LIGHT,
}