"""Support for Duwi Smart Binary Sensor."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import debounce
from .const import MANUFACTURER, DEBOUNCE, DEFAULT_ROOM, SLAVE
from . import DOMAIN

DUWI_BINARY_SENSOR_TYPES = ["human", "trigger"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Duwi config entry."""
    # Retrieve the instance ID from the configuration entry
    instance_id = config_entry.entry_id

    # Check if the DUWI_DOMAIN is loaded and has house_no available
    if DOMAIN in hass.data and "house_no" in hass.data[DOMAIN][instance_id]:
        # Access the SWITCH devices from the domain storage
        devices = hass.data[DOMAIN][instance_id]["devices"].get("binary_sensor")
        entities_to_add = []
        # If there are devices present, proceed with entity addition
        if devices is not None:
            for _type in DUWI_BINARY_SENSOR_TYPES:
                if _type in devices:
                    for device in devices[_type]:
                        common_attributes = {
                            "hass": hass,
                            "instance_id": instance_id,
                            "device_name": device.device_name,
                            "style": _type,
                            "device_no": device.device_no,
                            "house_no": device.house_no,
                            "room_name": device.room_name,
                            "floor_name": device.floor_name,
                            "terminal_sequence": device.terminal_sequence,
                            "route_num": device.route_num,
                            "available": device.value.get("online", False),
                            "device_class": device.value.get("device_class", {}).get(
                                _type
                            ),
                            "state_class": device.value.get("state_class", {}).get(
                                _type
                            ),
                            "state": device.value.get(
                                "trigger_state", device.value.get("human_state", False)
                            ),
                        }
                        entities_to_add.append(DuwiBinarySensor(**common_attributes))

        async_add_entities(entities_to_add)


class DuwiBinarySensor(BinarySensorEntity):
    """A Duwi Binary Sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        style: str,
        device_no: str,
        house_no: str,
        room_name: str,
        floor_name: str,
        terminal_sequence: str,
        route_num: str,
        device_name: str,
        state: bool,
        available: bool,
        device_class: BinarySensorDeviceClass,
        state_class: str | None = None,
    ) -> None:
        """Initialize the Duwi sensor."""
        self._attr_unique_id = f"{style}_{device_no}"
        self._attr_state_class = state_class
        self._attr_is_on = state
        self._attr_device_class = device_class

        self._hass = hass
        self._instance_id = instance_id
        self._available = available
        self._type = style
        self._device_no = device_no
        self._house_no = house_no
        self._room_name = room_name
        self._floor_name = floor_name
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self.entity_id = f"binary_sensor.duwi_{style}_{device_no}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=MANUFACTURER,
            name=(self._room_name + " " if self._room_name else "") + device_name,
            suggested_area=(
                self._floor_name + " " + self._room_name
                if self._room_name
                else DEFAULT_ROOM
            ),
        )

    async def async_added_to_hass(self):
        """Add update_device_state to HA data."""
        # self._hass.data[DOMAIN][self._instance_id].setdefault(self._device_no, {})
        self._hass.data[DOMAIN][self._instance_id].setdefault(
            self._device_no, {}
        ).setdefault("update_device_state", {})[self._type] = self.update_device_state

        # self._hass.data[DOMAIN][self._instance_id].setdefault(
        #     self._terminal_sequence, {}
        # )
        self._hass.data[DOMAIN][self._instance_id].setdefault(SLAVE, {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    async def update_device_state(self, action: str = None, **kwargs: Any):
        """Update the device state."""
        if "available" in kwargs:
            self._available = kwargs["available"]
        elif "state" in kwargs:
            self._attr_is_on = kwargs["state"]
        await self.async_write_ha_state_with_debounce()

    @debounce(DEBOUNCE)
    async def async_write_ha_state_with_debounce(self):
        """Write HA state with debounce."""
        self.schedule_update_ha_state()
