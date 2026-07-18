#!/usr/bin/env python3
"""iTag fleet health check — nodes, tag links, drop rates.

For the distributed ESPHome setup (esphome/itag-node.yaml): pings each node,
checks its tag-connected sensors in HA, and counts link drops per tag over the
history window. A tag connected nowhere is asleep/away/flat; a flappy tag is
usually sitting at the edge between two nodes.

Usage: itag_fleet_check.py [minutes_of_history]
Env:   HA_URL   (default http://homeassistant.local:8123)
       HA_TOKEN (or put the long-lived token in ~/.config/itag-fleet-token)
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

# EDIT: your nodes — name: (ip, HA entity prefix of the node's device)
NODES = {
    "kitchen": ("192.168.1.201", "kitchen_itag_node"),
    "bedroom": ("192.168.1.202", "bedroom_itag_node"),
    "office": ("192.168.1.203", "office_itag_node"),
}
# EDIT: your tags — letter: owner
TAGS = {"a": "Tag A", "b": "Tag B", "c": "Tag C"}

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")


def token() -> str:
    t = os.environ.get("HA_TOKEN", "").strip()
    if t:
        return t
    c = pathlib.Path.home() / ".config" / "itag-fleet-token"
    if c.exists() and c.stat().st_size:
        return c.read_text().strip()
    sys.exit("no HA token: set HA_TOKEN or write ~/.config/itag-fleet-token")


def api(path: str):
    req = urllib.request.Request(f"{HA_URL}{path}",
                                 headers={"Authorization": f"Bearer {token()}"})
    return json.load(urllib.request.urlopen(req, timeout=15))


def main() -> None:
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    states = {s["entity_id"]: s["state"] for s in api("/api/states")}
    alerts = []

    print(f"=== iTag fleet check ({datetime.now():%H:%M:%S}, last {minutes}m) ===")
    for name, (ip, prefix) in NODES.items():
        ping = subprocess.run(["ping", "-c1", "-W2", ip], capture_output=True).returncode == 0
        sensor_states = [states.get(f"binary_sensor.{prefix}_itag_{t}_connected", "missing") for t in TAGS]
        ha_ok = any(s not in ("missing", "unavailable") for s in sensor_states)
        holds = [TAGS[t] for t in TAGS
                 if states.get(f"binary_sensor.{prefix}_itag_{t}_connected") == "on"]
        print(f"{name:14} ping={'OK' if ping else 'FAIL':4} ha={'OK' if ha_ok else 'DOWN':4} holds={holds or '-'}")
        if not ha_ok:
            alerts.append(f"NODE DOWN: {name} (no HA connection{', no ping' if not ping else ''})")
        # ping-only failures are expected: BLE+wifi power-save makes ICMP lossy

    print("--- tags:")
    start = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    for t, owner in TAGS.items():
        room = states.get(f"sensor.tag_{t}_room", "?")
        drops = 0
        for name, (ip, prefix) in NODES.items():
            ent = f"binary_sensor.{prefix}_itag_{t}_connected"
            try:
                hist = api(f"/api/history/period/{start}?filter_entity_id={ent}&minimal_response&no_attributes")
                rows = hist[0] if hist else []
                drops += sum(1 for r in rows if r.get("state") == "off")
            except Exception:
                pass
        flag = " ⚠" if room == "Unknown" else ""
        print(f"tag {t} ({owner:6}): room={room:16} drops({minutes}m)={drops}{flag}")
        if room == "Unknown":
            alerts.append(f"TAG UNSEEN: {owner} connected nowhere (asleep/away/battery?)")
        if drops > minutes // 3:
            alerts.append(f"FLAPPY: {owner} {drops} drops in {minutes}m")

    print("--- verdict:", "ALERTS:" if alerts else "ALL HEALTHY")
    for a in alerts:
        print(" ", a)


main()
