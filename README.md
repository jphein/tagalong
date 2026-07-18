# itags

**$2 BLE keyfinders as room-aware buttons, find-my beepers, and presence sensors for Home Assistant — no cloud, no vendor app.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
![Platform: Home Assistant](https://img.shields.io/badge/platform-Home%20Assistant-41BDF5.svg)
![No cloud](https://img.shields.io/badge/cloud-none-success.svg)

The classic **"iTAG" anti-lost keyfinder** ([~$2–3 on AliExpress](https://www.aliexpress.us/item/3256810519199817.html))
is about the cheapest BLE device money can buy: a Telink chip, a CR2032, one button,
one beeper. This repo turns a handful of them into a whole-home **find-my network**
and **room-aware light switches** — the tag's button toggles the lights of whatever
room the tag is currently in.

📖 **[Project site & write-up →](https://jphein.github.io/itags/)**

## What's in here

| Component | What it does |
|---|---|
| **`custom_components/itag/`** | Native HA integration — config flow + Bluetooth auto-discovery, works through HA's Bluetooth stack (local adapter *or* ESPHome BLE proxies). Button events, find/stop beep, room / signal / battery sensors. |
| **`esphome/itag-node.yaml`** | The **distributed** setup: ESP32 nodes that race to hold each tag's GATT link with *contested claiming* — the node holding the link **is** the room. |
| **`ha-packages/itag_lights.yaml`** | Room-aware button→lights engine + find/stop scripts + per-tag room sensors (for the ESPHome setup). |
| **`dashboards/itags-dashboard.yaml`** | "Find My" style Lovelace dashboard. |
| **`tools/itag_fleet_check.py`** | Fleet health CLI — node status, who holds which tag, link drop rates. |

## The tag

| Property | Value |
|---|---|
| Chip family | Telink (advertises the `ffe0` vendor service) |
| Battery | CR2032 |
| Button | `ffe0/ffe1` **notify** — only delivered over a live GATT connection |
| Beep | Immediate Alert `1802/2a06` — write `0x01` to beep, `0x00` to stop |
| Link Loss | `1803/2a06` — beeps on disconnect unless set to `0x00` (both setups silence it) |
| Battery % | GATT `180F/2A19` on *some* variants (often the buttonless ones) |
| MAC | Random-static — **may rotate after a battery swap** |

The catch that shapes everything: **the button only works over a live GATT
connection.** Something has to hold a link to every tag, all the time.

## Two ways to run it

**1. The custom integration** (simplest — start here): HA holds one link per tag
through its Bluetooth stack. Install via [HACS](https://hacs.xyz) → custom
repository `jphein/itags` (type: integration), or copy `custom_components/itag/`
into your config. Tags auto-discover in Settings → Devices & Services. You get a
button event entity, Find/Stop buttons, and room/signal/battery sensors per tag —
details in [`custom_components/itag/README.md`](custom_components/itag/README.md).

**2. The ESPHome fleet** (multi-room room-presence): one ESP32 per room holds the
links instead. Every node hears a tag advertise and delays its connect attempt
proportionally to RSSI weakness (`delay = (-55 − rssi) × 80 ms`) — so the nearest
node wins the race, with zero coordination. Three weak link-RSSI samples in a row
release the tag for a closer node to claim. Room handoff follows you around the
house; the button toggles the *labeled* lights of the room the tag is in (HA label
`button_lights`). See [`esphome/itag-node.yaml`](esphome/itag-node.yaml) +
[`ha-packages/itag_lights.yaml`](ha-packages/itag_lights.yaml).

Both can coexist — e.g. the integration for a bag tag, the fleet for the family's
pocket tags. Mind the budget: each ESP32 holds ~3 active GATT connections.

## Find-my

Press a dashboard tile → the tag beeps wherever it is, and its room sensor tells
you where to walk. In the fleet setup the find script fires on **all** nodes in
parallel and the link-holder wins; in the integration it's one button.

## Fleet health

```
$ HA_TOKEN=... tools/itag_fleet_check.py 30
kitchen        ping=OK   ha=OK   holds=['Tag A']
bedroom        ping=OK   ha=OK   holds=['Tag B']
office         ping=OK   ha=OK   holds=-
tag a (Tag A ): room=Kitchen          drops(30m)=0
...
--- verdict: ALL HEALTHY
```

## Sister projects

- [smartring](https://jphein.github.io/smartring/) — a $10 BLE ring as identity-aware follow-me lighting
- [moyoung-watch](https://github.com/jphein/moyoung-watch) — MoYoung/DaFit smartwatch integration, solar watch faces, BLE CLI

## License

[AGPL-3.0](LICENSE)
