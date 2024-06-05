"""Support for Duwi Smart Light."""

from __future__ import annotations

import logging
from typing import Any

from duwi_smarthome_sdk.api.control import ControlClient
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.model.req.device_control import ControlDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    APP_VERSION,
    CLIENT_MODEL,
    CLIENT_VERSION,
    DOMAIN,
    MANUFACTURER,
    DEFAULT_ROOM,
    DEBOUNCE,
    APP_KEY,
    APP_SECRET,
    ACCESS_TOKEN,
    SLAVE,
)
from .util import debounce, persist_messages_with_status_code

# Initialize logger
_LOGGER = logging.getLogger(__name__)
# Define the light types supported by this integration
DUWI_LIGHT_TYPES = ["on", "dim", "temp", "dim_temp", "rgb", "rgbw", "rgbcw"]
# Define the color modes supported by various light types.
SUPPORTED_LIGHT_MODES = {
    "on": [ColorMode.ONOFF],
    "dim": [ColorMode.BRIGHTNESS],
    "temp": [ColorMode.COLOR_TEMP],
    "dim_temp": [ColorMode.COLOR_TEMP],
    "rgb": [ColorMode.HS],
    "rgbw": [ColorMode.HS],
    "rgbcw": [ColorMode.HS],
}
DUWI_COLOR_TEMP_RANGE_MIN = 3000
DUWI_COLOR_TEMP_RANGE_MAX = 6000
HA_COLOR_TEMP_RANGE_MIN = 153
HA_COLOR_TEMP_RANGE_MAX = 500


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Asynchronously set up Duwi devices as Home Assistant entities based on a configuration entry."""

    # Extract the instance id from the provided config entry.
    instance_id = config_entry.entry_id

    # Access house-specific information if available.
    if DOMAIN in hass.data and "house_no" in hass.data[DOMAIN][instance_id]:
        devices = hass.data[DOMAIN][instance_id].get("devices", {}).get("light")

        # Proceed if there are light devices available.
        if devices:
            for device_type in DUWI_LIGHT_TYPES:
                # Check if current device type is available in the devices dictionary.
                if device_type in devices:
                    for device in devices[device_type]:
                        # Compile common attributes for each device entity.
                        common_attributes = {
                            "hass": hass,
                            "instance_id": instance_id,
                            "device_name": device.device_name,
                            "device_no": device.device_no,
                            "house_no": device.house_no,
                            "room_name": device.room_name,
                            "floor_name": device.floor_name,
                            "terminal_sequence": device.terminal_sequence,
                            "route_num": device.route_num,
                            "light_type": device_type,
                            "state": device.value.get("switch", "off") == "on",
                            "is_group": bool(getattr(device, "device_group_no", None)),
                            "available": device.value.get("online", False),
                            "supported_color_modes": SUPPORTED_LIGHT_MODES[device_type],
                        }

                        # Append device-specific attributes according to its type.
                        if device_type in ["dim", "dim_temp"]:
                            common_attributes["brightness"] = int(
                                device.value.get("light", 0) / 100 * 255
                            )

                        if device_type in ["temp", "dim_temp", "rgbcw"]:
                            color_temp_range = device.value.get(
                                "color_temp_range",
                                {
                                    "min": DUWI_COLOR_TEMP_RANGE_MIN,
                                    "max": DUWI_COLOR_TEMP_RANGE_MAX,
                                },
                            )
                            min_ct, max_ct = color_temp_range.get(
                                "min", DUWI_COLOR_TEMP_RANGE_MIN
                            ), color_temp_range.get("max", DUWI_COLOR_TEMP_RANGE_MAX)
                            common_attributes["color_temp_range"] = [min_ct, max_ct]
                            common_attributes["ct"] = calculate_color_temperature(
                                device, min_ct, max_ct
                            )

                        if device_type in ["rgb", "rgbw", "rgbcw"]:
                            hs_color = extract_hs_color(device)
                            common_attributes["hs_color"] = hs_color
                            common_attributes["brightness"] = extract_brightness(device)
                            common_attributes["is_color_light"] = True

                        # Add the device as a new entity in Home Assistant.
                        async_add_entities([DuwiLight(**common_attributes)])


def calculate_color_temperature(device, min_ct, max_ct):
    """Calculate and return the color temperature value."""
    # Insert logic for color temperature calculation here.
    return (
        (
            (HA_COLOR_TEMP_RANGE_MAX - HA_COLOR_TEMP_RANGE_MIN)
            * ((max_ct - int(device.value.get("color_temp", 0))) / (max_ct - min_ct))
            + HA_COLOR_TEMP_RANGE_MIN
        )
        if device.value.get("color_temp")
        else 0
    )


def extract_hs_color(device):
    """Extract and return the HS color."""
    color_info = device.value.get("color", {"h": 0, "s": 0, "v": 0})
    return color_info["h"], color_info["s"]


def extract_brightness(device):
    """Extract and return the brightness."""
    color_info = device.value.get("color", {"h": 0, "s": 0, "v": 0})
    return int(color_info.get("v", 0) / 100 * 255)


class DuwiLight(LightEntity):
    """Initialize the DuwiLight entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        device_name: str,
        device_no: str,
        house_no: str,
        floor_name: str,
        room_name: str,
        light_type: str,
        terminal_sequence: str,
        route_num: str,
        state: bool,
        is_color_light: bool = False,
        is_group: bool = False,
        available: bool = False,
        brightness: int | None = None,
        ct: int | None = None,
        color_temp_range: list[int] | None = None,
        hs_color: tuple[int, int] | None = None,
        rgb_color: tuple[int, int] | None = None,
        rgbw_color: tuple[int, int, int, int] | None = None,
        rgbww_color: tuple[int, int, int, int, int] | None = None,
        supported_color_modes: set[ColorMode] | None = None,
    ) -> None:
        """Initialize the light."""
        self._attr_available = available
        self._attr_brightness = brightness
        self._attr_color_temp = ct
        self._attr_hs_color = hs_color
        self._attr_rgbw_color = rgbw_color
        self._attr_rgbww_color = rgbww_color
        self._attr_is_on = state
        self._attr_unique_id = device_no

        self._hass = hass
        self._device_no = device_no
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self._is_color_light = is_color_light
        self._house_no = house_no
        self._type = light_type
        self._color_temp_range = color_temp_range
        self._floor_name = floor_name
        self._room_name = room_name
        self._instance_id = instance_id
        self._is_group = is_group
        self._control = True
        self.entity_id = f"light.duwi_{device_no}"
        if hs_color:
            self._attr_color_mode = ColorMode.HS
        elif rgb_color:
            self._attr_color_mode = ColorMode.RGB
        elif rgbw_color:
            self._attr_color_mode = ColorMode.RGBW
        elif rgbww_color:
            self._attr_color_mode = ColorMode.RGBWW
        elif ct:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._supported_color_modes = supported_color_modes
        self._attr_supported_color_modes = supported_color_modes
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_no)},
            manufacturer=MANUFACTURER,
            name=(self._room_name + " " if self._room_name else "") + device_name,
            suggested_area=(
                self._floor_name + " " + self._room_name
                if self._room_name
                else DEFAULT_ROOM
            ),
        )
        self._cc = ControlClient(
            app_key=self._hass.data[DOMAIN][instance_id][APP_KEY],
            app_secret=self._hass.data[DOMAIN][instance_id][APP_SECRET],
            access_token=self._hass.data[DOMAIN][instance_id][ACCESS_TOKEN],
            app_version=APP_VERSION,
            client_version=CLIENT_VERSION,
            client_model=CLIENT_MODEL,
            is_group=is_group,
        )
        # Initialize Control Device
        self._cd = ControlDevice(
            device_no=self._device_no,
            house_no=self._house_no,
        )

    async def async_added_to_hass(self):
        # Storing the device number and the method to update the device state
        self._hass.data[DOMAIN][self._instance_id][self._device_no] = {
            "color_temp_range": self._color_temp_range,
            "update_device_state": self.update_device_state,
        }

        # If the slave goes offline, the corresponding device entity should also be taken offline
        self._hass.data[DOMAIN][self._instance_id].setdefault(SLAVE, {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        self._attr_is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            # Set brightness from kwargs if present
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            if self._is_color_light:
                # If it's a color light, adjust the color brightness accordingly
                self._cd.add_param_info(
                    "color",
                    {
                        "h": self.hs_color[0],
                        "s": self.hs_color[1],
                        "v": int(round(self._attr_brightness / 255 * 100)),
                    },
                )
            else:
                # If it's not a color light, just set the light brightness
                self._cd.add_param_info(
                    "light", int(round(self._attr_brightness / 255 * 100))
                )

        if ATTR_COLOR_TEMP in kwargs:
            # Handle setting of color temperature
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]
            # Perform appropriate conversion to device's color temperature
            self._cd.add_param_info(
                "color_temp",
                int(
                    (
                        self._color_temp_range[1]
                        - int(
                            (
                                (self._attr_color_temp - HA_COLOR_TEMP_RANGE_MIN)
                                * (
                                    self._color_temp_range[1]
                                    - self._color_temp_range[0]
                                )
                                / (HA_COLOR_TEMP_RANGE_MAX - HA_COLOR_TEMP_RANGE_MIN)
                            )
                        )
                    )
                    // 100.0
                    * 100
                ),
            )

        if ATTR_HS_COLOR in kwargs:
            # Directly set HS color from arguments
            self._attr_color_mode = ColorMode.HS
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
            self._cd.add_param_info(
                "color",
                {
                    "h": self._attr_hs_color[0],
                    "s": self._attr_hs_color[1],
                    "v": int(round(self._attr_brightness / 255 * 100)),
                },
            )
        if len(self._cd.commands) == 0:
            self._cd.add_param_info("switch", "on")
        await self.control_device()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._attr_is_on = False

        # Update Home Assistant about the new state after disabling polling
        self._cd.add_param_info("switch", "off")

        await self.control_device()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the light's current state."""
        if self._attr_is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    async def control_device(self):
        if self._control:
            status = await self._cc.control(self._cd)
            if status == Code.SUCCESS.value:
                self.async_write_ha_state()
            else:
                await persist_messages_with_status_code(hass=self._hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()
        self._cd.remove_param_info()

    async def update_device_state(self, action: str = None, **kwargs: Any):
        """Update the device state."""
        self._control = False
        if action == "turn_on":
            await self.async_turn_on(**kwargs)
        elif action == "turn_off":
            await self.async_turn_off(**kwargs)
        elif action == "toggle":
            await self.async_toggle(**kwargs)
        else:
            if "available" in kwargs:
                self._attr_available = kwargs["available"]
                self.async_write_ha_state()
        self._control = True

    def convert_to_ha_color_temp(self, duwi_ct):
        """Convert device-specific color temperature to HA color temperature."""
        if not self._color_temp_range:
            self._color_temp_range = [
                DUWI_COLOR_TEMP_RANGE_MIN,
                DUWI_COLOR_TEMP_RANGE_MAX,
            ]
        return (
            (
                (HA_COLOR_TEMP_RANGE_MAX - HA_COLOR_TEMP_RANGE_MIN)
                * (
                    (self._color_temp_range[1] - duwi_ct)
                    / (self._color_temp_range[1] - self._color_temp_range[0])
                )
                + HA_COLOR_TEMP_RANGE_MIN
            )
            if duwi_ct
            else 0
        )

    @debounce(DEBOUNCE)
    async def async_write_ha_state_with_debounce(self):
        """Write HA state with debounce."""
        self.async_write_ha_state()
