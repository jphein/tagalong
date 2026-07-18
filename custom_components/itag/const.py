"""Constants for the iTag BLE Tracker integration."""
from __future__ import annotations

DOMAIN = "itag"

DEFAULT_NAME = "iTag"
MANUFACTURER = "Telink (generic)"
MODEL = "iTAG anti-lost keyfinder"

# GATT layout of the classic Telink "iTAG" keyfinder.
#
# NOTE 0x2A06 (Alert Level) exists under BOTH 0x1802 and 0x1803 — always resolve
# it through its parent service, never by characteristic UUID alone.
BUTTON_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"     # Telink key service
BUTTON_CHAR = "0000ffe1-0000-1000-8000-00805f9b34fb"        # notify: button presses
IMMEDIATE_ALERT_SERVICE = "00001802-0000-1000-8000-00805f9b34fb"  # write 0x01 = beep
LINK_LOSS_SERVICE = "00001803-0000-1000-8000-00805f9b34fb"  # beeps on link drop unless 0x00
ALERT_LEVEL_CHAR = "00002a06-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"    # not all iTAG variants have it
BATTERY_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

EVENT_BUTTON = f"{DOMAIN}_button"

# The tag only reports button presses over a live GATT connection, so the
# coordinator holds one persistently (this is what the ESPHome fleet in this
# repo does per-node; here HA holds a single link through its best proxy).
TICK_SECONDS = 60            # coordinator tick: room freshness + battery due-check
BATTERY_INTERVAL = 12 * 3600  # re-read battery this often while connected
BUTTON_DEBOUNCE = 0.5        # a physical press can deliver several ffe1 notifies
RESCAN_WINDOW = 8.0          # seconds to stay disconnected during a room rescan

# Room tracking (same approach as the sister lefun_ring integration):
# while DISCONNECTED the room is the freshest/strongest advert's scanner; while
# CONNECTED the tag stops advertising, so the room is the proxy holding the link.
PROXY_ROOM_OVERRIDES: dict[str, str] = {}
ROOM_SWITCH_MARGIN = 8    # dBm a challenger must win by (anti flip-flop)
FRESH_WINDOW = 30.0       # a scanner only counts if it heard the tag this recently
RSSI_AGE_PENALTY = 1.0    # score = rssi - penalty * age_seconds

SERVICE_FIND = "find"
SERVICE_STOP = "stop"
