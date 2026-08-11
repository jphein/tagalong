# `itag` — the custom integration

Native Home Assistant integration for classic Telink **iTAG** BLE keyfinders.
Runs over HA's Bluetooth stack — a local adapter or any ESPHome Bluetooth proxy
with `active: true` connections. No YAML required.

## What you get per tag

| Entity | What it is |
|---|---|
| `event.<tag>_button` | The physical button (`ffe0/ffe1` notify) — also fired on the bus as `itag_button` with `address`, `name`, `room` |
| `button.<tag>_find` / `button.<tag>_stop_ringing` | Beep / silence (Immediate Alert `1802/2a06`) |
| `device_tracker.<tag>` | `home` while any proxy hears/holds the tag, `not_home` otherwise — add it to a **person** to track home/away |
| `sensor.<tag>_room` | Room = the proxy holding the GATT link (or the freshest/strongest scanner while disconnected) |
| `sensor.<tag>_signal` | Last advert RSSI (diagnostic) |
| `sensor.<tag>_battery` | GATT `180F` battery — only some iTAG variants expose it; stays unavailable otherwise |
| `binary_sensor.<tag>_connected` / `_ringing` | Link + beep state |
| `button.<tag>_rescan_room` | Drop the link ~8 s so the room can be re-derived from fresh advertisements |

Services: `itag.find` / `itag.stop` (optional `device_id`).

## Behavior notes

- The tag only reports button presses over a **live GATT connection**, so the
  integration holds one persistently and reconnects the moment the tag is heard
  advertising again. Each ESP32 proxy has ~3 active-connection slots — budget
  accordingly.
- On every connect it writes `0x00` to **Link Loss** (`1803/2a06`) first, so its
  own disconnects (rescan, reload, restart) never false-beep the tag.
- While connected the tag cannot advertise, so the room only re-derives on
  reconnect — press **Rescan room** after moving it, or use the distributed
  [ESPHome contested-claiming fleet](../../esphome/) for automatic multi-room
  handoff.
- `not_home` needs *no* proxy to hear the tag, so leaving takes up to a coordinator
  tick plus HA's stale-advertisement window (~2 min worst case). Arrival is
  immediate — the first advertisement flips it back to `home`.
- iTAG MACs are usually random-static: they can **rotate after a battery swap**.
  If a tag goes permanently unavailable after new batteries, re-add it.
