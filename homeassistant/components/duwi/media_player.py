"""Support for Duwi Smart Media_player."""

from __future__ import annotations

import logging
from typing import Any

from duwi_smarthome_sdk.api.control import ControlClient
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.model.req.device_control import ControlDevice

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import (
    APP_VERSION,
    CLIENT_MODEL,
    CLIENT_VERSION,
    DOMAIN,
    MANUFACTURER,
    APP_KEY,
    APP_SECRET,
    ACCESS_TOKEN,
    DEFAULT_ROOM,
    SLAVE,
    DEBOUNCE,
)
from .util import debounce, persist_messages_with_status_code

MUSIC_PLAYER_SUPPORT = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.STOP
)

HUA_ERSI_MUSIC = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

XIANG_WANG_MUSIC_S7_MINI_3S = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

XIANG_WANG_MUSIC_S8 = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

SHENG_BI_KE_MUSIC = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

BO_SHENG_MUSIC = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SOUND_MODE = "Music"

SUPPORTED_MEDIA_PLAYER_MODES = {
    "hua_ersi_music": HUA_ERSI_MUSIC,
    "xiang_wang_music_s7_mini_3s": XIANG_WANG_MUSIC_S7_MINI_3S,
    "xiang_wang_music_s8": XIANG_WANG_MUSIC_S8,
    "sheng_bi_ke_music": SHENG_BI_KE_MUSIC,
    "bo_sheng_music": BO_SHENG_MUSIC,
}


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
        devices = hass.data[DOMAIN][instance_id]["devices"].get("media_player")

        entities_to_add = []
        # If there are devices present, proceed with entity addition
        if devices:
            # Helper function to create DuwiSwitch entities
            for media_player_type in SUPPORTED_MEDIA_PLAYER_MODES:
                if media_player_type in devices:
                    for device in devices[media_player_type]:
                        singer = device.value.get(
                            "audio_full_info", device.value.get("audio_info", {})
                        ).get("singer")
                        singer_name = (
                            singer[0].get("name", "unknown singer")
                            if isinstance(singer, list) and singer and len(singer) > 0
                            else singer
                        )
                        common_attributes = {
                            "hass": hass,
                            "instance_id": instance_id,
                            "device_name": device.device_name,
                            "style": media_player_type,
                            "device_no": device.device_no,
                            "house_no": device.house_no,
                            "room_name": device.room_name,
                            "floor_name": device.floor_name,
                            "terminal_sequence": device.terminal_sequence,
                            "route_num": device.route_num,
                            "available": device.value.get("online", False),
                            "play": device.value.get("play", "off"),
                            "volume": device.value.get("volume", 0) / 100,
                            "mute": device.value.get("mute", "off") == "on",
                            "play_progress": device.value.get("play_progress", None),
                            "play_mode": device.value.get("play_mode", "list"),
                            "duration": device.value.get(
                                "duration",
                                device.value.get(
                                    "audio_full_info",
                                    device.value.get("audio_info", {}),
                                ).get("duration", "00:00"),
                            ),
                            "pic_url": device.value.get(
                                "audio_full_info", device.value.get("audio_info", {})
                            ).get("pic_url", ""),
                            "singer": singer_name,
                            "song_id": device.value.get(
                                "audio_full_info", device.value.get("audio_info", {})
                            ).get("song_id", ""),
                            "song_mid": device.value.get(
                                "audio_full_info", device.value.get("audio_info", {})
                            ).get("song_mid", ""),
                            "song_name": (
                                device.value.get("audio_full_info", {}).get("song_name")
                                or device.value.get("audio_info", {}).get("name")
                                or "unknown song"
                            ),
                            "supported_features": SUPPORTED_MEDIA_PLAYER_MODES[
                                media_player_type
                            ],
                        }
                        if (
                            media_player_type == "hua_ersi_music"
                            or media_player_type == "xiang_wang_music_s7_mini_3s"
                        ):
                            common_attributes["volume_max"] = 15
                        if (
                            media_player_type == "xiang_wang_music_s8"
                            or media_player_type == "bo_sheng_music"
                        ):
                            common_attributes["volume_max"] = 100
                        if media_player_type == "sheng_bi_ke_music":
                            common_attributes["volume_max"] = 19
                        new_entity = DuwiMusicPlayer(**common_attributes)
                        entities_to_add.append(new_entity)
            if entities_to_add:
                async_add_entities(entities_to_add)


class DuwiMusicPlayer(MediaPlayerEntity):
    """A Duwi media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        instance_id: str,
        device_no: str,
        style: str,
        terminal_sequence: str,
        route_num: str,
        house_no: str,
        room_name: str,
        floor_name: str,
        available: bool,
        device_name: str,
        play_progress: str,
        play_mode: str,
        play: str,
        volume: int,
        volume_max: int,
        mute: bool,
        duration: str,
        pic_url: str,
        singer: str,
        song_id: str,
        song_mid: str,
        song_name: str,
        supported_features: MediaPlayerEntityFeature | None,
        is_group: bool = False,
    ) -> None:
        """Initialize the Duwi device."""
        minutes, seconds = map(int, duration.split(":"))
        self._attr_media_artist = singer
        self._attr_media_title = song_name
        self._attr_available = available
        self._attr_volume_level = volume
        self._attr_is_volume_muted = mute
        self._attr_sound_mode = DEFAULT_SOUND_MODE
        self._attr_is_volume_muted = False
        self._attr_unique_id = device_no
        self._attr_media_content_id = song_id
        self._attr_media_content_type = MediaType.MUSIC
        self._attr_media_duration = minutes * 60 + seconds
        self._attr_media_image_url = pic_url
        self._attr_supported_features = supported_features
        self._attr_media_position_updated_at = dt_util.utcnow()
        self._attr_state = (
            MediaPlayerState.PLAYING if play == "on" else MediaPlayerState.PAUSED
        )
        if play_mode == "list":
            self._attr_repeat = RepeatMode.ALL
            self._attr_shuffle = False
        elif play_mode == "single":
            self._attr_repeat = RepeatMode.ONE
            self._attr_shuffle = False
        elif play_mode == "random":
            self._attr_repeat = RepeatMode.ALL
            self._attr_shuffle = True
        elif play_mode == "order":
            self._attr_repeat = RepeatMode.ALL
            self._attr_shuffle = False
        if play_progress:
            minutes, seconds = map(int, play_progress.split(":"))
            self._attr_media_position = minutes * 60 + seconds
        else:
            self._attr_media_position = 0

        self._hass = hass
        self._type = style
        self._progress: int | None = int(self._attr_media_duration * 0.15)
        self._instance_id = instance_id
        self._device_no = device_no
        self._terminal_sequence = terminal_sequence
        self._route_num = route_num
        self._house_no = house_no
        self._room_name = room_name
        self._floor_name = floor_name
        self._device_name = device_name
        self._volume_max = volume_max
        self._play_mode = play_mode
        self._pic_url = pic_url
        self._song_id = song_id
        self._song_mid = song_mid
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
        self._control = True
        self.entity_id = f"media_player.duwi_{device_no}"

        # Initialize Control Client
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
        self._cd = ControlDevice(device_no=self._device_no, house_no=self._house_no)

    async def async_added_to_hass(self):
        """Add update_device_state to HA data."""
        self._hass.data[DOMAIN][self._instance_id][self._device_no] = {
            "update_device_state": self.update_device_state,
        }

        self._hass.data[DOMAIN][self._instance_id].setdefault(SLAVE, {}).setdefault(
            self._terminal_sequence, {}
        )[self._device_no] = self.update_device_state

    async def async_media_play(self) -> None:
        """Send play command."""
        self._attr_state = MediaPlayerState.PLAYING
        # Update Home Assistant about the new state after disabling polling
        self._cd.add_param_info("play", "on")
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        sec = (dt_util.utcnow() - self._attr_media_position_updated_at).total_seconds()
        self._attr_media_position += sec
        self._attr_media_position_updated_at = dt_util.utcnow()
        self._attr_state = MediaPlayerState.PAUSED
        self._cd.add_param_info("play", "off")
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        self._attr_media_position = int(position)
        self._attr_media_position_updated_at = dt_util.utcnow()
        # Convert seconds to minutes and seconds
        minutes, seconds = divmod(int(position), 60)
        # Format the string as "00:00"
        time_str = "{:02d}:{:02d}".format(minutes, seconds)
        self._cd.add_param_info("play_progress", time_str)
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._attr_is_volume_muted = mute
        if mute:
            self._cd.add_param_info("mute", "on")
        else:
            self._cd.add_param_info("mute", "off")
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_volume_up(self) -> None:
        """Increase volume."""
        assert self.volume_level is not None
        self._attr_volume_level = min(1.0, self.volume_level + 0.1)
        volume = int(self._attr_volume_level * self._volume_max)
        self._cd.add_param_info("volume", volume)
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        assert self.volume_level is not None
        self._attr_volume_level = max(0.0, self.volume_level - 0.1)
        volume = int(self._attr_volume_level * self._volume_max)
        self._cd.add_param_info("volume", volume)
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level, range 0..1."""
        self._attr_volume_level = volume
        self._cd.add_param_info("volume", int(volume * self._volume_max))
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        self._attr_shuffle = shuffle
        if shuffle:
            self._attr_repeat = RepeatMode.ALL
            self._cd.add_param_info("play_mode", "random")
        else:
            await self.async_set_repeat(self._attr_repeat)
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Enable/disable repeat mode."""
        if repeat == RepeatMode.OFF and (self._type == "hua_ersi_music"):
            if self._attr_repeat == RepeatMode.ONE:
                self._attr_repeat = repeat = RepeatMode.ALL
            elif self._attr_repeat == RepeatMode.ALL:
                self._attr_repeat = RepeatMode.ONE
                self.schedule_update_ha_state()
                return
        if repeat == RepeatMode.ONE:
            self._attr_shuffle = False
        elif repeat == RepeatMode.ALL:
            self._attr_shuffle = False
        elif repeat == RepeatMode.OFF:
            self._attr_shuffle = False
        self._attr_repeat = repeat
        if repeat == RepeatMode.ONE:
            self._cd.add_param_info("play_mode", "single")
        elif repeat == RepeatMode.ALL:
            self._cd.add_param_info("play_mode", "list")
        else:
            self._cd.add_param_info("play_mode", "all")
            self._cd.add_param_info("play_mode", "order")
        await self.control_device()
        self.schedule_update_ha_state()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        self._cd.add_param_info("songs_switch", "prev")
        await self.control_device()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        self._cd.add_param_info("songs_switch", "next")
        await self.control_device()

    async def control_device(self):
        """Control the device by sending the control command."""
        if self._control:
            status = await self._cc.control(self._cd)
            if status == Code.SUCCESS.value:
                self.schedule_update_ha_state()
            else:
                await persist_messages_with_status_code(hass=self._hass, status=status)
        else:
            await self.async_write_ha_state_with_debounce()
        self._cd.remove_param_info()

    async def update_device_state(self, action: str = None, **kwargs: Any):
        """Update the device state."""
        self._control = False
        if action == "media_play":
            await self.async_media_play()
        elif action == "media_pause":
            await self.async_media_pause()
        elif action == "media_mute":
            await self.async_mute_volume(kwargs.get("media_mute", False))
        elif action == "volume_set":
            await self.async_set_volume_level(kwargs.get("volume_set", 0.5))
        elif action == "media_seek":
            await self.async_media_seek(kwargs.get("media_seek"))
        elif action == "play_mode":
            await self.async_set_repeat(kwargs.get("repeat_mode"))
            await self.async_set_shuffle(kwargs.get("shuffle"))
        elif action == "duration":
            self._attr_media_duration = kwargs.get("duration")
            await self.async_write_ha_state_with_debounce()
        elif action == "cut_song":
            self._attr_media_artist = kwargs.get("singer", "unknown singer")
            self._attr_media_title = kwargs.get("song_name", "unknown song")
            self._attr_media_image_url = kwargs.get("pic_url")
            self._attr_media_duration = kwargs.get("duration")
            self._attr_media_position = 0
            self._attr_media_position_updated_at = dt_util.utcnow()
            await self.async_write_ha_state_with_debounce()
        else:
            if "available" in kwargs:
                self._attr_available = kwargs["available"]
                await self.async_write_ha_state_with_debounce()
        self._control = True

    @debounce(DEBOUNCE)
    async def async_write_ha_state_with_debounce(self):
        """Write HA state with debounce."""
        self.schedule_update_ha_state()
