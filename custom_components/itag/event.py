"""Event entity for the tag's physical button."""
from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ITagCoordinator
from .entity import ITagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ITagCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ITagButtonEvent(coordinator)])


class ITagButtonEvent(ITagEntity, EventEntity):
    _attr_name = "Button"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["press"]

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "button")
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub = self.coordinator.register_button_listener(self._handle_press)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_press(self) -> None:
        self._trigger_event("press")
        self.async_write_ha_state()
