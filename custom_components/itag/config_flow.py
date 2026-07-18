"""Config flow for the iTag BLE Tracker — Bluetooth discovery or manual pick."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (BluetoothServiceInfoBleak,
                                                async_discovered_service_info)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import BUTTON_SERVICE, DEFAULT_NAME, DOMAIN


def _is_itag(info: BluetoothServiceInfoBleak) -> bool:
    if BUTTON_SERVICE in (uuid.lower() for uuid in info.service_uuids):
        return True
    return (info.name or "").lower().startswith("itag")


class ITagConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an iTag."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a tag discovered via the Bluetooth stack (through a proxy)."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or DEFAULT_NAME}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery.name or DEFAULT_NAME,
                data={CONF_ADDRESS: self._discovery.address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._discovery.name or DEFAULT_NAME,
                "address": self._discovery.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered tag, or enter its address manually.

        Manual entry matters because a tag reached only through an ESPHome proxy
        may be connectable while its forwarded advertisement carries no service
        UUIDs — the ffe0 discovery match can miss it even though HA can connect.
        """
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered.get(address)
            return self.async_create_entry(
                title=(info.name if info else None) or DEFAULT_NAME,
                data={CONF_ADDRESS: address},
            )

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current or not _is_itag(info):
                continue
            self._discovered[info.address] = info

        if self._discovered:
            address_selector: Any = vol.In(
                {addr: f"{info.name or DEFAULT_NAME} ({addr})"
                 for addr, info in self._discovered.items()}
            )
        else:
            address_selector = str  # nothing matched — let the user type the MAC directly

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): address_selector}),
        )
