"""Binary sensors: GATT link held, and ringing."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (BinarySensorDeviceClass,
                                                    BinarySensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ITagCoordinator
from .entity import ITagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ITagCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ITagConnectedSensor(coordinator), ITagRingingSensor(coordinator)])


class ITagConnectedSensor(ITagEntity, BinarySensorEntity):
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected


class ITagRingingSensor(ITagEntity, BinarySensorEntity):
    _attr_name = "Ringing"
    _attr_device_class = BinarySensorDeviceClass.SOUND
    _attr_icon = "mdi:bell-ring"

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "ringing")

    @property
    def is_on(self) -> bool:
        return self.coordinator.ringing
