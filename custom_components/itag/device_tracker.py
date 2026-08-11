"""Device tracker: home while any proxy hears/holds the tag, not_home when none do.

Exists so a tag can be attached to a `person` — carry it and you're home.
The room sensor says *where*; this only answers home/away.
"""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ITagCoordinator
from .entity import ITagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ITagCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ITagDeviceTracker(coordinator)])


class ITagDeviceTracker(ITagEntity, BaseTrackerEntity):
    """`room == "away"` (no scanner heard it, no link held) is the only not_home."""

    _attr_name = None  # the tracker *is* the device -> device_tracker.<tag>
    _attr_source_type = SourceType.BLUETOOTH_LE

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "tracker")

    @property
    def state(self) -> str:
        # ponytail: away lags by up to one tick + HA's stale-advert window (~2 min
        # worst case). Add an explicit away timer only if that's too slow/jumpy.
        room = (self.coordinator.data or {}).get("room")
        return STATE_NOT_HOME if room in (None, "away") else STATE_HOME
