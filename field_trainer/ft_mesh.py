"""
BATMAN-adv mesh + wifi probing utilities, isolated behind a small API.

All subprocess parsing is contained here so other modules don't need to know
about `batctl`/`iwconfig` quirks or formats.
"""

import subprocess
from typing import Any, Dict, List

from .ft_version import VERSION


def _safe_run(cmd: list[str], timeout: float = 10.0) -> str:
    """
    Run a shell command defensively, return stdout or "" on failure.

    We deliberately do not raise to keep the UI responsive even when tools
    are missing or the environment is not mesh-enabled.
    """
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout if res.returncode == 0 else ""
    except Exception:
        return ""


def mac_to_device_name(mac: str) -> str:
    """
    Map MAC address to friendly device name. Extend this map with real devices.

    Fallback: Identify Raspberry Pi OUI and mark unknown others.
    """
    mac_mappings = {
        "b8:27:eb:a7:e0:81": "Device 0 (Gateway)",
        "b8:27:eb:60:3c:54": "Device 1",
        "b8:27:eb:bd:c0:8f": "Device 2",
        "b8:27:eb:7f:03:d9": "Device 3",
        "b8:27:eb:40:ea:f8": "Device 4",
        "b8:27:eb:1e:e1:94": "Device 5",
    }
    if not mac:
        return "Unknown"
    if mac in mac_mappings:
        return mac_mappings[mac]
    if mac.startswith("b8:27:eb"):  # Raspberry Pi OUI
        return f"Pi Device ({mac[-8:]})"
    return f"Unknown ({mac})"


def get_batman_mesh_info() -> Dict[str, Any]:
    """
    Collect mesh info using `batctl` (text mode) and return a structured dict.

    We parse:
     - originators
     - neighbors
     - statistics
    and build a `summary` block for quick status checks.
    """
    mesh_info: Dict[str, Any] = {
        "mesh_nodes": [],
        "neighbor_details": [],
        "mesh_statistics": {},
        "summary": {},
    }

    # originators
    out = _safe_run(["batctl", "meshif", "bat0", "originators"])
    if out:
        for line in out.strip().splitlines():
            if not line or line.startswith("[") or "Originator" in line:
                continue
            parts = line.split()
            if len(parts) >= 4:
                originator = parts[0]
                last_seen_str = parts[1]  # e.g., "0.123s"
                tq_str = parts[2].strip("()")
                next_hop = parts[3]
                iface = parts[4].strip("[]") if len(parts) > 4 else "unknown"

                try:
                    last_seen_ms = int(float(last_seen_str.rstrip("s")) * 1000)
                except Exception:
                    last_seen_ms = 0
                try:
                    tq = int(tq_str)
                except Exception:
                    tq = 0

                mesh_info["mesh_nodes"].append({
                    "mac_address": originator,
                    "last_seen": last_seen_ms,
                    "next_hop": next_hop,
                    "outgoing_interface": iface,
                    "link_quality": {"tq": tq, "tt_crc": None},
                    "device_name": mac_to_device_name(originator),
                })

    # neighbors
    out = _safe_run(["batctl", "meshif", "bat0", "neighbors"])
    if out:
        for line in out.strip().splitlines():
            if not line or "Neighbor" in line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                neighbor_mac = parts[0]
                last_seen_str = parts[1]
                tq_str = parts[2].strip("()")
                iface = parts[3].strip("[]") if len(parts) > 3 else "wlan0"
                try:
                    last_seen_ms = int(float(last_seen_str.rstrip("s")) * 1000)
                except Exception:
                    last_seen_ms = 0
                try:
                    tq = int(tq_str)
                except Exception:
                    tq = 0
                mesh_info["neighbor_details"].append({
                    "mac_address": neighbor_mac,
                    "interface": iface,
                    "link_quality": tq,
                    "last_seen": last_seen_ms,
                    "device_name": mac_to_device_name(neighbor_mac),
                    "is_direct_neighbor": True,
                })

    # statistics
    out = _safe_run(["batctl", "meshif", "bat0", "statistics"])
    if out:
        stats: Dict[str, str] = {}
        for line in out.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                stats[key.strip()] = value.strip()
        mesh_info["mesh_statistics"] = stats

    # summary
    mesh_info["summary"] = {
        "total_mesh_nodes": len(mesh_info["mesh_nodes"]),
        "direct_neighbors": len(mesh_info["neighbor_details"]),
        "mesh_active": len(mesh_info["mesh_nodes"]) > 0,
        "collection_method": "batman-adv text parsing",
    }
    return mesh_info


def get_gateway_status() -> Dict[str, Any]:
    """
    Merge wifi (wlan0/wlan1) and BATMAN info into a single status dict
    consumed by the web/UI. This isolates all subprocess calls here.
    """
    status: Dict[str, Any] = {
        "mesh_active": False,
        "mesh_ssid": "Unknown",
        "mesh_cell": "Unknown",
        "batman_neighbors": 0,
        "batman_neighbors_list": [],
        "mesh_devices": [],
        "mesh_statistics": {},
        "wlan1_ssid": "Not connected",
        "wlan1_ip": "Not assigned",
        "uptime": "Unknown",
        "version": VERSION,
    }

    # wlan0 info
    out = _safe_run(["iwconfig", "wlan0"], timeout=5.0)
    if out:
        for line in out.splitlines():
            if "ESSID:" in line:
                essid = line.split("ESSID:")[1].strip().strip('"')
                if essid != "off/any":
                    status["mesh_ssid"] = essid
                    status["mesh_active"] = True
            if "Cell:" in line:
                cell = line.split("Cell:")[1].split()[0].strip()
                status["mesh_cell"] = cell

    # BATMAN info
    mesh_info = get_batman_mesh_info()
    status["batman_neighbors"] = mesh_info["summary"].get("total_mesh_nodes", 0)
    status["batman_neighbors_list"] = [
        {
            "mac": node["mac_address"],
            "last_seen": f"{node['last_seen']/1000:.3f}s",
            "interface": node.get("outgoing_interface", "wlan0"),
            "link_quality": node["link_quality"]["tq"],
        }
        for node in mesh_info["mesh_nodes"]
    ]
    # devices
    for node in mesh_info["mesh_nodes"]:
        status["mesh_devices"].append({
            "device_name": node["device_name"],
            "mac_address": node["mac_address"],
            "connection_quality": node["link_quality"]["tq"],
            "last_seen_ms": node["last_seen"],
            "is_direct_neighbor": any(n["mac_address"] == node["mac_address"] for n in mesh_info["neighbor_details"]),
            "status": "Active" if node["last_seen"] < 30000 else "Stale",  # 30s threshold
            "routing_via": node.get("next_hop", "Direct"),
        })
    status["mesh_statistics"] = mesh_info["mesh_statistics"]

    # wlan1 (internet uplink) info
    out = _safe_run(["iwconfig", "wlan1"], timeout=5.0)
    if out:
        for line in out.splitlines():
            if "ESSID:" in line:
                essid = line.split("ESSID:")[1].strip().strip('"')
                if essid != "off/any":
                    status["wlan1_ssid"] = essid
    out = _safe_run(["ip", "addr", "show", "wlan1"], timeout=5.0)
    if out:
        for line in out.splitlines():
            if "inet " in line and "scope global" in line:
                ip = line.strip().split()[1].split("/")[0]
                status["wlan1_ip"] = ip

    # uptime from /proc/uptime
    try:
        with open("/proc/uptime", "r") as f:
            seconds = float(f.readline().split()[0])
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        status["uptime"] = f"{hours}h {minutes}m"
    except Exception:
        pass

    return status
