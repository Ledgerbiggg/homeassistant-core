"""Support for Duwi Smart Cover."""

from __future__ import annotations

import logging
from typing import Any

from duwi_smarthome_sdk.api.control import ControlClient
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.model.req.device_control import ControlDevice

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CLIENT_MODEL,
    APP_VERSION,
    CLIENT_VERSION,
    MANUFACTURER,
    DEBOUNCE,
    DEFAULT_ROOM,
    APP_KEY,
    APP_SECRET,
    ACCESS_TOKEN,
    SLAVE,
)
from .util import debounce, persist_messages_with_status_code

_LOGGER = logging.getLogger(__name__)

# Supported types of Duwi Covers
DUWI_COVER_TYPES = ["roll", "shutter"]

# Define supported features for each cover type:
SUPPORTED_COVER_MODES = {
    "roll": (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    ),
    "shutter": (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Duwi cover platform based on the configuration entry."""

    # Use the entry_id to access the specific instance information.
    instance_id = config_entry.entry_id

    # Ensure the relevant domain data is available for this instance.
    if DOMAIN in hass.data and "house_no" in hass.data[DOMAIN][instance_id]:
        # Retrieve the devices classified under 'COVER' for the instance.
        devices = hass.data[DOMAIN][instance_id].get("devices", {}).get("cover")

        # Prepare a list to accumulate entities to add.
        entities_to_add = []

        if devices:  # Check if devices exist.
            # Iterate over each cover type defined in DUWI_COVER_TYPES.
            for cover_type in DUWI_COVER_TYPES:
                # Check if there are devices for the current cover type.
                if cover_type in devices:
                    for device in devices[cover_type]:
                        # Set common attributes to pass to the entity.
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
                            "state": device.value.get("switch", "off") == "on",
                            "is_group": bool(getattr(device, "device_group_no", None)),
                            "available": device.value.get("online"),
                            "position": int(device.value.get("control_percent", 0)),
                            "supported_features": SUPPORTED_COVER_MODES[cover_type],
                        }

                        # Handle special attributes and features for shutters.
                        if cover_type == "shutter":
                            tilt_position = int(
                                device.value.get(
                                    "angle_degree", device.value.get("light_angle", 0)
                                )
                            )
                            # Adjust tilt position if necessary.
                            if tilt_position > 90:
                                tilt_position -= 90
                            # Convert to percentage.
                            _LOGGER.debug("tilt_position: %s", tilt_position)
                            common_attributes["tilt_position"] = (
                                int(tilt_position / 90 * 100) / 10.0
                            )

                        # Instantiate the cover entity with common attributes.
                        new_entity = DuwiCover(**common_attributes)
                        # Append the new entity to the list of entities to add.
                        entities_to_add.append(new_entity)

            # Add all prepared entities to Home Assistant.
            if entities_to_add:
                async_add_entities(entities_to_add)


class DuwiCover(CoverEntity):
    """A Duwi Cover device. Inherits from Home Assistant's CoverEntity class."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        device_no: str,
        terminal_sequence: str,
        route_num: str,
        device_name: str,
        house_no: str,
        floor_name: str,
        room_name: str,
        state: bool,
        available: bool,
        is_group: bool = False,
        position: int | None = None,
        tilt_position: int | None = None,
        supported_features: CoverEntityFeature | None = None,
    ) -> None:
        """Initialize the DuwiCover entity."""
        self._attr_available = available
        self._attr_current_cover_position = position
        self._attr_supported_features = supported_features
        self._attr_current_cover_tilt_position = tilt_position
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = position is None or position <= 0

        self._hass = hass
        self._attr_unique_id = device_no
        self._device_no = device_no
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self._device_name = device_name
        self._house_no = house_no
        self._floor_name = floor_name
        self._room_name = room_name
        self._route_num = route_num
        self._state = state
        self._instance_id = instance_id
        self._is_group = is_group
        self._set_position = None
        self._set_tilt_position = None
        self._requested_closing = True
        self._requested_closing_tilt = True
        self._unsub_listener_cover = None
        self._unsub_listener_cover_tilt = None
        self._control = True
        # Setting the entity's unique ID based on the device number.
        self.entity_id = f"cover.duwi_{device_no}"

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
            app_key=hass.data[DOMAIN][instance_id][APP_KEY],
            app_secret=hass.data[DOMAIN][instance_id][APP_SECRET],
            access_token=hass.data[DOMAIN][instance_id][ACCESS_TOKEN],
            app_version=APP_VERSION,
            client_version=CLIENT_VERSION,
            client_model=CLIENT_MODEL,
            is_group=is_group,
        )

        self._cd = ControlDevice(device_no=self._device_no, house_no=self._house_no)

    async def async_added_to_hass(self):
        # Storing the device number and the method to update the device state
        self._hass.data[DOMAIN][self._instance_id][self.unique_id] = {
            "update_device_state": self.update_device_state,
        }

        # If the slave goes offline, the corresponding device entity should also be taken offline
        self._hass.data[DOMAIN][self._instance_id].setdefault(SLAVE, {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover completely."""
        # Set the position to 0 indicating closed cover.
        self._attr_current_cover_position = 0
        # Update the cover control parameters.
        self._cd.add_param_info(
            "control_percent", int(self._attr_current_cover_position)
        )
        # If the action is not scheduled, send control command.
        await self.control_device()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the tilt of the cover."""
        # Set the tilt position to 0 indicating closed tilt.
        self._attr_current_cover_tilt_position = 0
        # Update the cover tilt parameters.
        self._cd.add_param_info("angle_degree", int(self._attr_current_cover_position))
        self._cd.add_param_info("light_angle", int(self._attr_current_cover_position))
        # Similar control mechanism as in async_close_cover.
        await self.control_device()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover completely."""
        # Set the position to 100 indicating fully open cover.
        self._attr_current_cover_position = 100
        # Update the cover control parameters.
        self._cd.add_param_info(
            "control_percent", int(self._attr_current_cover_position)
        )
        # Similar control mechanism as in async_close_cover.
        await self.control_device()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the tilt of the cover."""
        # Set the tilt position to 100 indicating fully open tilt.
        self._attr_current_cover_tilt_position = 100
        # Calculate and update the tilt angles.
        self._cd.add_param_info(
            "angle_degree", int(self._attr_current_cover_tilt_position / 100 * 90)
        )
        self._cd.add_param_info(
            "light_angle", int(self._attr_current_cover_tilt_position / 100 * 90)
        )
        # Similar control mechanism as in async_close_cover.
        await self.control_device()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        # Get the target position from the service call.
        position: int = kwargs[ATTR_POSITION]
        # Store the position internally.
        self._attr_current_cover_position = position
        # Send the position parameter to the device.
        self._cd.add_param_info(
            "control_percent", int(self._attr_current_cover_position)
        )
        # Direct control or state update based on scheduled flag.
        await self.control_device()
        self._attr_is_closed = (
            self.current_cover_position and self.current_cover_position <= 0
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        # Retrieve and store the desired tilt position.
        tilt_position: int = kwargs[ATTR_TILT_POSITION]
        self._attr_current_cover_tilt_position = tilt_position
        # Calculate and send the angle to the device.
        self._cd.add_param_info(
            "angle_degree", int(self._attr_current_cover_tilt_position / 100 * 90)
        )
        self._cd.add_param_info(
            "light_angle", int(self._attr_current_cover_tilt_position / 100 * 90)
        )
        # Direct control or state update based on scheduled flag.
        await self.control_device()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover from moving."""
        # Add a stop control command parameter.
        self._cd.add_param_info("control", "stop")
        # Send control command or state update based on scheduled action.
        await self.control_device()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the movement of the cover's tilt."""
        # This follows the same logic as the stop cover method.
        self._cd.add_param_info("control", "stop")
        await self.control_device()

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
        """Update the device state based on the given action."""
        # A dispatch method for various actions.
        self._control = False
        if action == "set_cover_position":
            await self.async_set_cover_position(**kwargs)
        elif action == "set_cover_tilt_position":
            await self.async_set_cover_tilt_position(**kwargs)
        else:
            # General state update handling.
            if "available" in kwargs:
                self._attr_available = kwargs["available"]
                self.async_write_ha_state()
        self._control = True

    @debounce(DEBOUNCE)
    async def async_write_ha_state_with_debounce(self):
        """Write HA state with debounce."""
        self.async_write_ha_state()
