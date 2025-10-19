"""
Optional: background connection monitor (log-only).
Safe to import; nothing runs unless you call start_connection_monitor().
"""

import threading
import time
from .ft_registry import REGISTRY


def start_connection_monitor(interval_secs: int = 30) -> None:
    """Every interval, log a brief connection summary."""
    def run():
        while True:
            time.sleep(interval_secs)
            with REGISTRY.nodes_lock:
                active = [nid for nid, n in REGISTRY.nodes.items() if n._writer is not None]
                offline = [nid for nid, n in REGISTRY.nodes.items() if n._writer is None and n.status != "Unknown"]
            if active or offline:
                REGISTRY.log(f"Connection status - Active: {len(active)}, Offline: {len(offline)}")
                if offline:
                    REGISTRY.log(f"Offline devices: {', '.join(offline)}", level="warning")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    REGISTRY.log("Connection monitoring started")
