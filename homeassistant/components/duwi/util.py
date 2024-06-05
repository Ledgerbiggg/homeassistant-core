"""Utility methods for the Duwi Smart Hub integration"""

import asyncio
import json
import logging
from typing import Callable, Optional

from duwi_smarthome_sdk.const.status import Code

from homeassistant.components.media_player import RepeatMode
from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DUWI_SENSOR_VALUE_REFLECT_HA_SENSOR_TYPE

_LOGGER = logging.getLogger(__name__)


async def trans_duwi_state_to_ha_state(
    hass: HomeAssistant, instance_id: str, message: str
):
    """Synchronize the entity's state in Home Assistant based on the received message."""

    # Ignore KEEPALIVE messages as they do not contain state information.
    if message == "KEEPALIVE":
        return

    # Attempting to parse the JSON message.
    try:
        message_data = json.loads(message)
    except json.JSONDecodeError:
        return

    namespace = message_data.get("namespace")

    # Proceed only with the expected namespaces.
    if namespace not in [
        "Duwi.RPS.DeviceValue",
        "Duwi.RPS.TerminalOnline",
        "Duwi.RPS.DeviceGroupValue",
    ]:
        return

    # Checking for a result within the message.
    result = message_data.get("result")
    if not result:
        return

    # Parsing the result if it's a string.
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return

    msg = result.get("msg")
    if not msg:
        return

    # Handling TerminalOnline namespace separately.
    if namespace == "Duwi.RPS.TerminalOnline":
        sequence = msg.get("sequence")
        is_online = msg.get("online")

        # If the slave is offline, then all devices under this slave are offline
        device_updates = (
            hass.data[DOMAIN][instance_id].get("slave", {}).get(sequence, None)
        )
        if device_updates and (
            hass.data[DOMAIN][instance_id]
            .get("slave", {})
            .get(sequence, {})
            .get("is_follow_online")
            or not is_online
        ):
            for device_no, handler in device_updates.items():
                if callable(handler):
                    await handler(available=is_online)
            return
        # If the host is offline, all devices of all slaves under the slave devices will be offline
        terminals = hass.data[DOMAIN][instance_id].get("host", {}).get(sequence)
        if terminals and not is_online:
            for terminal in terminals:
                device_updates = (
                    hass.data[DOMAIN][instance_id].get("slave", {}).get(terminal)
                )

                if device_updates:
                    for device_no, handler in device_updates.items():
                        if callable(handler):
                            await handler(available=is_online)
        return

    # Extract device number and retrieve entity ID from Home Assistant data.
    device_no = msg.get("deviceNo", msg.get("deviceGroupNo"))
    if not device_no:
        return

    if device_no not in hass.data[DOMAIN][instance_id]:
        return

    # Prepare the action and attributes based on the message.
    action = "turn_on" if msg.get("switch") != "off" else "turn_off"

    attr_dict = {}

    # Process light-specific attributes.
    if msg.get("online"):
        action = None
        attr_dict["available"] = msg.get("online")
    if msg.get("light"):
        attr_dict["brightness"] = int(round(msg.get("light") / 100 * 255))
    if msg.get("color_temp"):
        color_temp_range = (
            hass.data[DOMAIN][instance_id].get(device_no, {}).get("color_temp_range")
        )
        ct = 500 - (int(round(msg.get("color_temp"))) - color_temp_range[0]) * (
            500 - 153
        ) / (color_temp_range[1] - color_temp_range[0])
        attr_dict["color_temp"] = int(ct)
    if msg.get("color"):
        color_info = msg.get("color")
        hs_color = (color_info["h"], color_info["s"])
        brightness = int((color_info["v"] / 100) * 255)
        if brightness == 0:
            action = "turn_off"
        attr_dict["brightness"] = brightness
        attr_dict["hs_color"] = hs_color

    # Process cover-specific attributes.
    if msg.get("control_percent"):
        action = "set_cover_position"
        attr_dict["position"] = msg.get("control_percent")
    if msg.get("light_angle") or msg.get("angle_degree"):
        action = "set_cover_tilt_position"
        angle = msg.get("light_angle", msg.get("angle_degree"))
        attr_dict["tilt_position"] = (180 - angle if angle > 90 else angle) / 90 * 100

    # Process media-player-specific attributes.
    if msg.get("play"):
        if msg.get("play") == "on":
            action = "media_play"
        elif msg.get("play") == "off":
            action = "media_pause"
    if msg.get("mute"):
        action = "media_mute"
        attr_dict["media_mute"] = msg.get("mute") == "on"
    if msg.get("volume"):
        action = "volume_set"
        attr_dict["volume_set"] = msg.get("volume") / 100
    if msg.get("play_mode"):
        action = "play_mode"
        if msg.get("play_mode") == "random":
            _LOGGER.debug("play_mode: random")
            attr_dict["shuffle"] = True
            attr_dict["repeat_mode"] = RepeatMode.ALL
        elif msg.get("play_mode") == "list":
            attr_dict["shuffle"] = False
            attr_dict["repeat_mode"] = RepeatMode.ALL
        elif msg.get("play_mode") == "single":
            attr_dict["shuffle"] = False
            attr_dict["repeat_mode"] = RepeatMode.ONE
        elif msg.get("play_mode") == "order" or msg.get("play_mode") == "all":
            attr_dict["shuffle"] = False
            attr_dict["repeat_mode"] = RepeatMode.OFF
    if msg.get("play_progress"):
        action = "media_seek"
        minutes, seconds = map(int, msg.get("play_progress", "00:00").split(":"))
        attr_dict["media_seek"] = minutes * 60 + seconds
    if msg.get("audio_full_info") or msg.get("audio_info"):
        action = "cut_song"
        info = (
            msg.get("audio_full_info")
            if msg.get("audio_full_info")
            else msg.get("audio_info")
        )
        if info.get("singer", [{"name": "unknown singer"}])[0]:
            attr_dict["singer"] = info.get("singer", [{"name": "unknown singer"}])[
                0
            ].get("name")
        if info.get("song_name", "unknown song"):
            attr_dict["song_name"] = info.get("song_name")
        if info.get("pic_url"):
            attr_dict["pic_url"] = info.get("pic_url")
        if msg.get("duration"):
            minutes, seconds = map(int, msg.get("duration", "00:00").split(":"))
            attr_dict["duration"] = minutes * 60 + seconds
    else:
        if msg.get("duration"):
            action = "duration"
            minutes, seconds = map(int, msg.get("duration", "00:00").split(":"))
            attr_dict["duration"] = minutes * 60 + seconds

    # Update method for obtaining entities
    device = hass.data[DOMAIN][instance_id][device_no]
    update_device = device.get("update_device_state")
    if not update_device:
        _LOGGER.debug("No update_device_state")
        return
    # The situation where the device is divided into multiple entities
    if isinstance(update_device, dict):
        for key in DUWI_SENSOR_VALUE_REFLECT_HA_SENSOR_TYPE:
            if key in msg:
                attr_dict["state"] = msg.get(key)
                await update_device.get(
                    DUWI_SENSOR_VALUE_REFLECT_HA_SENSOR_TYPE.get(key)
                )(action, **attr_dict)
    else:
        # Update entity status
        await update_device(action=action, **attr_dict)


async def persist_messages_with_status_code(
    hass: HomeAssistant, status: Optional[str] = None, message: Optional[str] = None
) -> None:
    """Persists messages with specific status code."""
    messages = {
        Code.SUCCESS.value: "Success",
        Code.SYS_ERROR.value: "System Error",
        Code.LOGIN_ERROR.value: "Login Error",
        Code.APP_KEY_ERROR.value: "App Key Error",
        Code.TIMESTAMP_TIMEOUT.value: "Timestamp Timeout",
        Code.SYSTEM_RATE_LIMIT.value: "System Rate Limit",
        Code.SYSTEM_MINUTE_RATE_LIMIT.value: "System Minute Rate Limit",
        Code.SYSTEM_HOUR_RATE_LIMIT.value: "System Hour Rate Limit",
        Code.GATEWAY_SYS_ERROR.value: "Gateway System Error",
    }

    if not message and status:
        message = messages.get(status, "Unknown error" + str(status))

    if message is None:
        return

    async_create_notification(
        hass=hass,
        message=message,
        title="Duwi Notification",
        notification_id="duwi_notification",
    )


def debounce(wait: int or float) -> Callable:
    """Decorator to debounce function calls."""

    def decorator(fn):
        async def debounced_fn(self, *args, **kwargs):
            if hasattr(self, "_debounce_timer") and self._debounce_timer:
                self._debounce_timer.cancel()

            async def delayed_execution():
                await asyncio.sleep(wait)
                await fn(self, *args, **kwargs)

            self._debounce_timer = asyncio.create_task(delayed_execution())

        return debounced_fn

    return decorator
