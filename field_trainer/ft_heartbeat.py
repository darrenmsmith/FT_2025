"""
TCP heartbeat server that devices connect to.

Exposes:
- start_heartbeat_server() -> returns the server instance
  (call .shutdown() in your main on exit)
"""

import json
import socket
import socketserver
import threading
from typing import Any, Dict, Optional

from .ft_config import HOST, HEARTBEAT_TCP_PORT, READ_TIMEOUT_SECS
from .ft_models import utcnow_iso
from .ft_registry import REGISTRY


class HeartbeatHandler(socketserver.StreamRequestHandler):
    """Read JSON lines from devices and reply with assignments/status."""

    def setup(self) -> None:
        # Keep-alive helps detect dead connections
        self.request.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except (OSError, AttributeError):
            pass
        self.request.settimeout(READ_TIMEOUT_SECS)
        super().setup()

    def handle(self) -> None:
        peer_ip = self.client_address[0]
        node_id: Optional[str] = None
        REGISTRY.log(f"Device connected from {peer_ip}")

        try:
            while True:
                try:
                    line = self.rfile.readline()
                    if not line:
                        REGISTRY.log(f"Device {peer_ip} closed connection cleanly")
                        break
                    try:
                        msg = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError as e:
                        REGISTRY.log(f"Invalid JSON from {peer_ip}: {e}", level="error")
                        self._send_error("Invalid JSON format")
                        continue

                    node_id = msg.get("node_id") or peer_ip
                    # Upsert node (maps 'role'->'action' if present)
                    REGISTRY.upsert_node(
                        node_id=node_id,
                        ip=peer_ip,
                        writer=self.wfile,
                        status=msg.get("status", "Unknown"),
                        ping_ms=msg.get("ping_ms"),
                        hops=msg.get("hops"),
                        sensors=msg.get("sensors", {}),
                        accelerometer_working=msg.get("accelerometer_working", False),
                        audio_working=msg.get("audio_working", False),
                        battery_level=msg.get("battery_level"),
                        action=msg.get("action"),
                    )

                    self._send_ok(node_id)

                except socket.timeout:
                    REGISTRY.log(f"Timeout from device {peer_ip} - connection may be dead", level="warning")
                    break
                except (ConnectionResetError, BrokenPipeError):
                    REGISTRY.log(f"Device {peer_ip} connection error/reset")
                    break
                except Exception as e:
                    REGISTRY.log(f"Handler error for {peer_ip}: {e}", level="error")
                    break
        finally:
            self._cleanup(node_id, peer_ip)

    # ----- replies -----

    def _send_ok(self, node_id: str) -> None:
        data = {
            "ack": True,
            "action": REGISTRY.assignments.get(node_id),
            "course_status": REGISTRY.course_status,
            "timestamp": utcnow_iso(),
            "mesh_network": "ft_mesh",
            # keep a small surface in handler: no VERSION import here
        }
        self._send(data)

    def _send(self, data: Dict[str, Any]) -> None:
        payload = (json.dumps(data) + "\n").encode("utf-8")
        self.wfile.write(payload)
        self.wfile.flush()

    def _send_error(self, message: str) -> None:
        try:
            self._send({"error": message, "timestamp": utcnow_iso()})
        except Exception:
            pass

    def _cleanup(self, node_id: Optional[str], peer_ip: str) -> None:
        if node_id:
            REGISTRY.log(f"Device {node_id} ({peer_ip}) disconnected")
            with REGISTRY.nodes_lock:
                if node_id in REGISTRY.nodes:
                    REGISTRY.nodes[node_id]._writer = None
        else:
            REGISTRY.log(f"Unknown device {peer_ip} disconnected")


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    """Thread-per-connection server with fast shutdown behavior."""
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls):
        super().__init__(server_address, handler_cls)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)
        REGISTRY.log(f"TCP server configured for mesh network on {server_address}")

    def serve_forever(self, poll_interval=0.5):
        try:
            REGISTRY.log("TCP server ready for device connections")
            super().serve_forever(poll_interval=poll_interval)
        except KeyboardInterrupt:
            REGISTRY.log("TCP server interrupted, shutting down...")
            self.shutdown()


def start_heartbeat_server():
    """
    Start the threaded heartbeat TCP server in a background thread.

    Returns:
        The server instance; call .shutdown() from your main on exit.
    """
    srv = ThreadedTCPServer((HOST, HEARTBEAT_TCP_PORT), HeartbeatHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    REGISTRY.log(f"Heartbeat server started on {HOST}:{HEARTBEAT_TCP_PORT}")
    REGISTRY.log("Ready for Device 1-5 connections via wlan0 mesh")
    return srv
