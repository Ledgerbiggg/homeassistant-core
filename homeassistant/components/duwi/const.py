"""Constants for the Duwi integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
    PERCENTAGE,
    ILLUMINANCE,
    CONCENTRATION_PARTS_PER_MILLION,
)

# Unique domain identifier for the Duwi Smart Hub integration
DOMAIN = "duwi"

# Manufacturer of the product for identification purposes
MANUFACTURER = "Duwi"

# Version of the App for the Duwi Smart Hub integration, used for tracking and compatibility.
APP_VERSION = "0.1.1"

# Home Assistant client version
CLIENT_VERSION = "0.1.1"

# Model identification of the Home Assistant client, typically used for logging or diagnostics.
CLIENT_MODEL = "homeassistant"

# API keys
APP_KEY = "app_key"
APP_SECRET = "app_secret"
ACCESS_TOKEN = "access_token"
REFRESH_TOKEN = "refresh_token"

HOST = "host"
SLAVE = "slave"
HOUSE_NO = "house_no"
DEFAULT_ROOM = "default room"
DEBOUNCE = 0.5
SENSOR_TYPE = "7"

# List of platforms that support config entry
SUPPORTED_PLATFORMS = [
    Platform.SWITCH,
]


SENSOR_TYPE_DICT = {
    "temperature": {
        "type": "sensor",
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "humidity": {
        "type": "sensor",
        "unit_of_measurement": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "light": {
        "type": "sensor",
        "unit_of_measurement": ILLUMINANCE,
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "formaldehyde": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "pm25": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "carbon_dioxide": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "air_quality": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.AQI,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "carbon_monoxide": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "tvoc": {
        "type": "sensor",
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "trigger": {
        "type": "binary_sensor",
        "unit_of_measurement": None,
        "device_class": BinarySensorDeviceClass.OPENING,
        "state_class": None,
    },
    "human": {
        "type": "binary_sensor",
        "device_class": BinarySensorDeviceClass.MOTION,
        "state_class": None,
    },
}
SENSOR_ATTR_DICT = {
    "carbon_dioxide": "co2_value",
    "pm25": "pm25_value",
    "tvoc": "tvoc_value",
    "carbon_monoxide": "co_value",
    "humidity": "humidity_value",
    "formaldehyde": "hcho_value",
    "temperature": "temp_value",
    "light": "bright_value",
    "air_quality": "iaq_value",
}

DUWI_SENSOR_VALUE_REFLECT_HA_SENSOR_TYPE = {
    "temp_value": "temperature",
    "humidity_value": "humidity",
    "bright_value": "light",
    "hcho_value": "formaldehyde",
    "pm25_value": "pm25",
    "co2_value": "carbon_dioxide",
    "iaq_value": "air_quality",
    "co_value": "carbon_monoxide",
    "tvoc_value": "tvoc",
    "human_state": "human",
    "trigger_state": "trigger",
}
