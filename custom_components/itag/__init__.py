"""The iTag BLE Tracker integration.

Turns the classic $2 Telink "iTAG" keyfinder into a room-aware button, a
find-my beeper, and a presence sensor — over HA's Bluetooth stack (local
adapter or ESPHome Bluetooth proxies with active connections).
"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SERVICE_FIND, SERVICE_STOP
from .coordinator import ITagCoordinator, ITagError

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.EVENT, Platform.SENSOR]

# Optional device target on services; if omitted and only one tag is configured, it's used.
_TARGET = {vol.Optional("device_id"): cv.string}


def _resolve(hass: HomeAssistant, call: ServiceCall) -> ITagCoordinator:
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("No iTag is configured")
    device_id = call.data.get("device_id")
    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device:
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    for coord in entries.values():
                        if coord.address == identifier[1]:
                            return coord
        raise HomeAssistantError(f"device_id {device_id} is not an iTag")
    if len(entries) == 1:
        return next(iter(entries.values()))
    raise HomeAssistantError("Multiple iTags configured — pass device_id")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = ITagCoordinator(hass, entry.data[CONF_ADDRESS], entry.title)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: ITagCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
        if not hass.data[DOMAIN]:
            for svc in (SERVICE_FIND, SERVICE_STOP):
                hass.services.async_remove(DOMAIN, svc)
    return unloaded


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_FIND):
        return

    async def _guard(coro):
        try:
            return await coro
        except ITagError as err:
            raise HomeAssistantError(str(err)) from err

    async def find(call: ServiceCall) -> None:
        await _guard(_resolve(hass, call).async_find())

    async def stop(call: ServiceCall) -> None:
        await _guard(_resolve(hass, call).async_stop_ringing())

    hass.services.async_register(DOMAIN, SERVICE_FIND, find, schema=vol.Schema(_TARGET))
    hass.services.async_register(DOMAIN, SERVICE_STOP, stop, schema=vol.Schema(_TARGET))
