"""Buttons: find (beep), stop, and rescan room."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ITagCoordinator
from .entity import ITagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ITagCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ITagFindButton(coordinator),
        ITagStopButton(coordinator),
        ITagRescanButton(coordinator),
    ])


class ITagFindButton(ITagEntity, ButtonEntity):
    _attr_name = "Find"
    _attr_icon = "mdi:bell-ring"

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "find")

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_find()
        except Exception as err:  # noqa: BLE001 — surface BLE errors in the UI
            raise HomeAssistantError(f"Find failed: {err}") from err


class ITagStopButton(ITagEntity, ButtonEntity):
    _attr_name = "Stop ringing"
    _attr_icon = "mdi:bell-off"

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "stop")

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_stop_ringing()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Stop failed: {err}") from err


class ITagRescanButton(ITagEntity, ButtonEntity):
    """Drop the link briefly so the room can be re-derived from fresh adverts."""

    _attr_name = "Rescan room"
    _attr_icon = "mdi:map-marker-down"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "rescan")

    async def async_press(self) -> None:
        await self.coordinator.async_rescan_room()
