# tagalong — design (2026-07-18)

> Renamed `itags` → `tagalong` same day: avoids the Apple-adjacent i-prefix
> and sidesteps the HACS `tags/`-suffix URL-mangle bug the first name uncovered.

## Goal

Extract the iTag A/B/C system from the private `~/Projects/ha` workspace into a
public repo (`jphein/tagalong`) with a native custom integration and a GitHub Pages
write-up, following the smartring / moyoung-watch pattern.

## Decisions

- **Native integration** (`custom_components/itag/`, domain `itag`), modeled on
  `lefun_ring`: config flow + bluetooth discovery (`ffe0` / `iTAG*`), coordinator
  holds a persistent GATT link through HA's Bluetooth stack (ESPHome proxies with
  active connections). Chosen over a thin wrapper around `esphome.itag_button`
  events because it gives outsiders a zero-YAML adoption path.
- **Production stays on the ESPHome fleet.** JP's A/B/C tags keep the distributed
  contested-claiming model; the sanitized node config ships in `esphome/` as the
  advanced setup. No prod changes in this ship.
- **Hybrid room tracking** in the integration: advert-scanner scoring (freshness +
  hysteresis, cribbed from lefun_ring) while disconnected; the link-holding proxy
  while connected; a "Rescan room" button drops the link briefly to re-derive.
- **Link-loss silencing** (`1803/2a06 = 0x00`) on every connect so integration
  disconnects never false-beep (learned in ibags).
- **Sanitization**: `!secret` for ESPHome keys/passwords, placeholder MACs,
  no family names/rooms, no LAN details.
- **Not live-tested** on ship day: installing a new custom component needs an HA
  restart (unattended prod change — declined). Validated via hassfest + HACS CI.

## Layout

`custom_components/itag/` · `esphome/itag-node.yaml` · `ha-packages/itag_lights.yaml`
· `dashboards/tagalong-dashboard.yaml` · `tools/itag_fleet_check.py` · `docs/`
(GitHub Pages) · `hacs.json` · AGPL-3.0.

## Follow-ups

- Live-test the integration against a real tag (needs a coordinated HA restart;
  candidate: the ibags tag, brief connects only).
- Consider an options flow (auto-rescan interval, room overrides).
