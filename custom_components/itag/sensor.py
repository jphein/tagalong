"""Sensors: room, signal strength, battery (when the tag variant exposes 180F)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ITagCoordinator
from .entity import ITagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ITagCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ITagRoomSensor(coordinator),
        ITagRssiSensor(coordinator),
        ITagBatterySensor(coordinator),
    ])


class ITagRoomSensor(ITagEntity, SensorEntity):
    """Which room the tag is in — the proxy holding/hearing it."""

    _attr_name = "Room"
    _attr_icon = "mdi:map-marker-radius"

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "room")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("room")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "nearest_proxy": data.get("nearest_proxy"),
            "last_seen": data.get("last_seen"),
        }


class ITagRssiSensor(ITagEntity, SensorEntity):
    _attr_name = "Signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "rssi")

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("nearest_rssi")


class ITagBatterySensor(ITagEntity, SensorEntity):
    """Battery % via GATT 180F/2A19 — stays unavailable on variants without it."""

    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ITagCoordinator) -> None:
        super().__init__(coordinator, "battery")

    @property
    def available(self) -> bool:
        return super().available and (self.coordinator.data or {}).get("battery") is not None

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("battery")
