"""Connection + room coordinator for an iTag, over HA's Bluetooth stack.

HA routes ``bleak`` connections through whatever ESPHome Bluetooth proxy (active
connections) is in radio range, so no local adapter is needed. Unlike a device
that can stay passive, an iTag only reports button presses over a live GATT
link — so this coordinator holds one persistently, reconnecting whenever the
tag is heard advertising again.

Room tracking is two-mode:
- disconnected: freshest/strongest advertisement wins (scanner scoring with an
  age penalty + switch hysteresis, shared approach with the lefun_ring sister
  integration);
- connected: the tag stops advertising, so the room is the proxy that holds
  the link (refresh it on demand with the "Rescan room" button).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Callable, Optional

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import close_stale_connections, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (ALERT_LEVEL_CHAR, BATTERY_CHAR, BATTERY_INTERVAL, BATTERY_SERVICE,
                    BUTTON_CHAR, BUTTON_DEBOUNCE, DOMAIN, EVENT_BUTTON, FRESH_WINDOW,
                    IMMEDIATE_ALERT_SERVICE, LINK_LOSS_SERVICE, PROXY_ROOM_OVERRIDES,
                    RESCAN_WINDOW, ROOM_SWITCH_MARGIN, RSSI_AGE_PENALTY, TICK_SECONDS)

_LOGGER = logging.getLogger(__name__)


class ITagError(Exception):
    """A recoverable iTag connection/command error."""


def proxy_to_room(name: Optional[str]) -> Optional[str]:
    """Derive a friendly room from a proxy/scanner name (``kitchen-ble-proxy`` -> Kitchen)."""
    if not name:
        return None
    base = name.split(" (")[0].strip()
    if base in PROXY_ROOM_OVERRIDES:
        return PROXY_ROOM_OVERRIDES[base]
    r = base
    for suf in ("-ble-proxy", "_ble_proxy", "bluetooth-proxy", "-tag-node", "_tag_node"):
        r = r.replace(suf, " ")
    parts = [p for p in r.replace("-", " ").replace("_", " ").split() if p]
    if len(parts) > 1 and parts[-1].isdigit():
        parts = parts[:-1]
    return " ".join(parts).title() or base


class ITagCoordinator(DataUpdateCoordinator):
    """Owns the BLE connection to one tag and exposes its operations."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=TICK_SECONDS))
        self.address = address.upper()
        self.device_name = name
        self._client: Optional[BleakClient] = None
        self._lock = asyncio.Lock()
        self._stopping = False
        self._conn_task: Optional[asyncio.Task] = None
        self._kick = asyncio.Event()          # wake the connection loop early
        self._bt_unsub = None                 # advertisement callback unsubscribe
        self._suspend_until = 0.0             # rescan: don't reconnect before this
        self._last_room: Optional[str] = None
        self._last_proxy: Optional[str] = None
        self._last_rssi: Optional[int] = None
        self._connected_via: Optional[str] = None  # scanner name holding the link
        self._ringing = False
        self._battery: Optional[int] = None
        self._battery_supported: Optional[bool] = None  # None = not yet probed
        self._battery_read_at = 0.0
        self._last_button_at = 0.0
        self._button_listeners: list[Callable[[], None]] = []

    # ---------------------------------------------------------------- lifecycle
    async def async_start(self) -> None:
        """Begin advert tracking and the persistent-connection loop."""
        if self._bt_unsub is None:
            self._bt_unsub = bluetooth.async_register_callback(
                self.hass, self._on_advertisement,
                bluetooth.BluetoothCallbackMatcher(address=self.address),
                bluetooth.BluetoothScanningMode.ACTIVE)
        if self._conn_task is None:
            self._conn_task = self.hass.async_create_background_task(
                self._connection_loop(), name=f"{DOMAIN}_connection_{self.address}")

    async def async_stop(self) -> None:
        self._stopping = True
        if self._bt_unsub is not None:
            self._bt_unsub()
            self._bt_unsub = None
        if self._conn_task is not None:
            self._conn_task.cancel()
            self._conn_task = None
        await self.async_disconnect()

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def ringing(self) -> bool:
        return self._ringing

    def register_button_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._button_listeners.append(cb)
        return lambda: self._button_listeners.remove(cb)

    # ---------------------------------------------------------------- connection
    def _on_disconnect(self, _client: BleakClient) -> None:
        self._client = None
        self._connected_via = None
        self._ringing = False
        self._kick.set()
        self.hass.loop.call_soon_threadsafe(self._push)

    async def _connection_loop(self) -> None:
        """Hold a GATT link whenever the tag is reachable; adverts kick retries early."""
        backoff = 5
        while not self._stopping:
            now = self.hass.loop.time()
            if not self.connected and now >= self._suspend_until:
                dev = bluetooth.async_ble_device_from_address(self.hass, self.address, True)
                if dev is not None:  # only try when something hears it — no churn while away
                    try:
                        async with self._lock:
                            await self._ensure_connected()
                        backoff = 5
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("reconnect failed: %s", err)
                        backoff = min(backoff * 2, 120)
            self._kick.clear()
            try:
                # Connected: sleep until kicked (disconnect). Disconnected: backoff,
                # but a fresh advertisement kicks an immediate retry.
                await asyncio.wait_for(self._kick.wait(),
                                       timeout=3600 if self.connected else backoff)
            except asyncio.TimeoutError:
                pass

    async def _ensure_connected(self) -> None:
        if self.connected:
            return
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True)
        if ble_device is None:
            raise ITagError(
                f"{self.address} not reachable via any Bluetooth proxy/adapter "
                "(tag asleep/away, or no proxy with free active-connection slots?)")
        await close_stale_connections(ble_device)
        client = await establish_connection(
            BleakClient, ble_device, self.address, disconnected_callback=self._on_disconnect)
        self._client = client
        self._connected_via = self._resolve_connection_source(ble_device)
        # Silence Link Loss (1803/2A06 = 0x00) FIRST: otherwise every disconnect we
        # cause (rescan, unload, HA restart) would beep the tag.
        try:
            svc = client.services.get_service(LINK_LOSS_SERVICE)
            if svc is not None:
                char = svc.get_characteristic(ALERT_LEVEL_CHAR)
                if char is not None:
                    await client.write_gatt_char(char, b"\x00", response=True)
        except Exception:  # noqa: BLE001 — best effort
            _LOGGER.debug("link-loss silencing failed (non-fatal)")
        try:
            await client.start_notify(BUTTON_CHAR, self._on_button_notify)
        except Exception as err:  # noqa: BLE001 — some clones lack ffe1; keep the link anyway
            _LOGGER.warning("button notify subscribe failed on %s: %s", self.address, err)
        await self._read_battery()
        self._push()

    def _resolve_connection_source(self, ble_device: BLEDevice) -> Optional[str]:
        """Name of the proxy/scanner the link runs through (habluetooth stamps it)."""
        try:
            source = (ble_device.details or {}).get("source")
            if source:
                scanner = bluetooth.async_scanner_by_source(self.hass, source)
                if scanner is not None:
                    return scanner.name or source
                return source
        except Exception:  # noqa: BLE001 — details layout is backend-specific
            pass
        return self._last_proxy

    async def async_disconnect(self) -> None:
        if self._client is not None and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001 — releasing is best-effort
                pass
        self._client = None
        self._connected_via = None

    # ---------------------------------------------------------------- button
    def _on_button_notify(self, _char, _data: bytearray) -> None:
        """A physical press: one press can deliver several ffe1 notifies — debounce."""
        now = self.hass.loop.time()
        if now - self._last_button_at < BUTTON_DEBOUNCE:
            return
        self._last_button_at = now
        room = (self.data or {}).get("room")
        _LOGGER.debug("button press on %s (room=%s)", self.address, room)
        self.hass.bus.async_fire(EVENT_BUTTON, {
            "address": self.address, "name": self.device_name, "room": room})
        for cb in list(self._button_listeners):
            cb()
        data = dict(self.data or {})
        data["last_button"] = dt_util.utcnow()
        self.async_set_updated_data(data)

    # ---------------------------------------------------------------- operations
    async def async_find(self) -> None:
        """Beep the tag (Immediate Alert = 0x01), connecting first if needed."""
        async with self._lock:
            if not self.connected:
                self._suspend_until = 0.0
                await self._ensure_connected()
            await self._write_alert(b"\x01")
            self._ringing = True
        self._push()

    async def async_stop_ringing(self) -> None:
        async with self._lock:
            if not self.connected:
                self._ringing = False
                self._push()
                return
            await self._write_alert(b"\x00")
            self._ringing = False
        self._push()

    async def _write_alert(self, value: bytes) -> None:
        svc = self._client.services.get_service(IMMEDIATE_ALERT_SERVICE)
        if svc is None:
            raise ITagError("tag has no Immediate Alert service")
        char = svc.get_characteristic(ALERT_LEVEL_CHAR)
        # Immediate Alert's Alert Level is write-without-response by spec
        await self._client.write_gatt_char(char, value, response=False)

    async def async_rescan_room(self) -> None:
        """Drop the link so the tag advertises again, then reconnect via the best proxy."""
        async with self._lock:
            self._suspend_until = self.hass.loop.time() + RESCAN_WINDOW
            await self.async_disconnect()
        self._push()
        # adverts arriving during the window update the room; the loop reconnects after

    # ---------------------------------------------------------------- battery
    async def _read_battery(self) -> None:
        """Opportunistic: many iTAG variants (incl. tags without buttons) expose 180F."""
        if self._battery_supported is False or self._client is None:
            return
        try:
            svc = self._client.services.get_service(BATTERY_SERVICE)
            if svc is None:
                self._battery_supported = False
                return
            raw = await self._client.read_gatt_char(svc.get_characteristic(BATTERY_CHAR))
            self._battery = int(raw[0])
            self._battery_supported = True
            self._battery_read_at = self.hass.loop.time()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("battery read failed: %s", err)

    # ---------------------------------------------------------------- room tracking
    def _recompute_location(self, data: dict) -> bool:
        """Fill location fields; return True if the room changed.

        Disconnected: freshest/strongest scanner wins (age-penalised score with
        switch hysteresis). Connected: the tag can't advertise, so the proxy
        holding the link is the room.
        """
        prev_room = data.get("room")
        if self.connected:
            room = proxy_to_room(self._connected_via)
            if room:
                self._last_room, self._last_proxy = room, self._connected_via
            data["room"] = self._last_room or "connected"
            data["nearest_proxy"] = self._connected_via or self._last_proxy
            data["nearest_rssi"] = self._last_rssi
            data["last_seen"] = dt_util.utcnow()
            return data.get("room") != prev_room

        now = self.hass.loop.time()
        proxies: dict[str, int] = {}
        ages: dict[str, float] = {}
        for sd in bluetooth.async_scanner_devices_by_address(self.hass, self.address, False):
            adv = sd.advertisement
            if adv is None or adv.rssi is None:
                continue
            name = sd.scanner.name or sd.scanner.source
            proxies[name] = adv.rssi
            ts = getattr(sd.scanner, "discovered_device_timestamps", {}).get(self.address)
            if ts is not None:
                ages[name] = now - ts

        fresh = {n: r for n, r in proxies.items() if ages.get(n, 1e9) < FRESH_WINDOW}
        if proxies and not ages:  # habluetooth without timestamps: degrade to cache-only
            fresh = dict(proxies)

        def score(name: str) -> float:
            return fresh[name] - RSSI_AGE_PENALTY * ages.get(name, 0.0)

        if fresh:
            nearest = max(fresh, key=score)
            chosen = nearest
            if self._last_proxy in fresh and nearest != self._last_proxy:
                if score(nearest) - score(self._last_proxy) < ROOM_SWITCH_MARGIN:
                    chosen = self._last_proxy
            self._last_room = proxy_to_room(chosen)
            self._last_proxy, self._last_rssi = chosen, fresh[chosen]
            data["room"] = self._last_room or "unknown"
            data["nearest_proxy"] = chosen
            data["nearest_rssi"] = fresh[chosen]
            data["last_seen"] = dt_util.utcnow()
        elif proxies:
            # between adverts — hold the last-known room rather than flapping
            data["room"] = self._last_room or "unknown"
            data["nearest_proxy"] = self._last_proxy
            data["nearest_rssi"] = self._last_rssi
        else:
            data["room"] = "away"
            data["nearest_proxy"] = None
            data["nearest_rssi"] = None
        return data.get("room") != prev_room

    @callback
    def _on_advertisement(self, service_info, _change) -> None:
        """A scanner heard the tag: update the room now and kick a reconnect."""
        if service_info.rssi is not None:
            self._last_rssi = service_info.rssi
        data = dict(self.data or {})
        changed = self._recompute_location(data)
        if not self.connected:
            self._kick.set()  # it's advertising -> it's reachable -> reconnect
        if changed:
            self.async_set_updated_data(data)

    # ---------------------------------------------------------------- data
    def _push(self) -> None:
        """Recompute + notify listeners outside the tick."""
        data = dict(self.data or {})
        self._fill(data)
        self.async_set_updated_data(data)

    def _fill(self, data: dict) -> None:
        self._recompute_location(data)
        data["connected"] = self.connected
        data["ringing"] = self._ringing
        data["battery"] = self._battery
        data["battery_supported"] = self._battery_supported

    async def _async_update_data(self) -> dict:
        data = dict(self.data or {})
        if (self.connected and self._battery_supported is not False
                and self.hass.loop.time() - self._battery_read_at > BATTERY_INTERVAL):
            async with self._lock:
                await self._read_battery()
        self._fill(data)
        return data
