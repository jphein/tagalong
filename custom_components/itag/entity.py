"""Shared entity base for the iTag integration."""
from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import ITagCoordinator


class ITagEntity(CoordinatorEntity[ITagCoordinator]):
    """One entity of one tag; the device groups them per tag."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ITagCoordinator, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(dr.CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
