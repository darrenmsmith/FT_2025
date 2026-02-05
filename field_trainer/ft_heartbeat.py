"""
Threaded TCP heartbeat server for device connections.

Protocol:
- Devices connect and send newline-delimited JSON heartbeats.
- We update Registry with every heartbeat.
- We reply with newline-delimited JSON containing:
    ack, action, course_status, timestamp (ISO), master_time (ms), mesh_network
  and, when available: led_pattern, audio_clip (to converge device state).

Notes:
- The server returns a handle with .shutdown(); the launcher uses this on exit.
- We fail soft on bad JSON to keep server resilient.
"""

import json
import socket
import time
import socketserver
import threading
from typing import Any, Dict, Optional

from .ft_config import HOST, HEARTBEAT_TCP_PORT, READ_TIMEOUT_SECS, TIME_SYNC_DRIFT_MS, TIME_SYNC_ON_CONNECT
from .ft_models import utcnow_iso
from .ft_registry import REGISTRY
from .ft_version import VERSION


class HeartbeatHandler(socketserver.StreamRequestHandler):
    """Handle a single device connection (one thread per connection)."""

    def setup(self) -> None:
        # Enable TCP keepalive where supported to detect dead peers
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
                        REGISTRY.log(f"Device {peer_ip} closed connection")
                        break

                    # Each frame is newline-delimited JSON
                    try:
                        msg = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError as e:
                        REGISTRY.log(f"Invalid JSON from {peer_ip}: {e}", level="error")
                        self._send_error("Invalid JSON format")
                        continue

                    node_id = msg.get("node_id") or peer_ip

                    # Update registry state for this device
                    # Determine display status based on course state
                    cs = REGISTRY.course_status
                    has_action = node_id in REGISTRY.assignments
                    if cs == "Active" and has_action:
                        display_status = "Active"
                    elif cs == "Deployed" and has_action:
                        display_status = "Deployed"
                    else:
                        display_status = "Standby"
                    
                    # FIX: Do NOT accept led_pattern from device heartbeats
                    # LED patterns flow server → device only, set via REGISTRY.set_led()
                    # Devices were sending None, clearing server-assigned colors
                    REGISTRY.upsert_node(
                        node_id=node_id,
                        ip=peer_ip,
                        writer=self.wfile,
                        status=display_status,
                        ping_ms=msg.get("ping_ms"),
                        hops=msg.get("hops"),
                        sensors=msg.get("sensors", {}),
                        accelerometer_working=msg.get("accelerometer_working", False),
                        audio_working=msg.get("audio_working", False),
                        battery_level=msg.get("battery_level"),
                        action=msg.get("action"),
                        # led_pattern: REMOVED - server controls this via set_led(), not devices
                        # audio_clip: REMOVED - server controls this via play_audio(), not devices
                        clock_skew_ms=msg.get("clock_skew_ms"),
                        # Phase 1: Touch event support
                        touch_detected=msg.get("touch_detected", False),
                        touch_timestamp=msg.get("touch_timestamp"),
                    )                    
                    # Handle touch events (Phase 1)
                    if msg.get('touch_detected'):
                        touch_timestamp = msg.get('touch_timestamp', time.time())
                        # Handle asynchronously to not block heartbeat
                        import threading
                        threading.Thread(
                            target=REGISTRY.handle_touch_event,
                            args=(node_id, touch_timestamp),
                            daemon=True
                        ).start()

                    # Optional time-drift correction trigger (if device reports skew)
                    try:
                        skew = msg.get("clock_skew_ms")
                        if isinstance(skew, (int, float)) and abs(int(skew)) > TIME_SYNC_DRIFT_MS:
                            REGISTRY.sync_time(node_id)
                    except Exception:
                        pass

                    # Optional initial sync on (inferred) first connect: caller can send a flag,
                    # or we can infer by absence of previous state. Keep this minimal for now.
                    if TIME_SYNC_ON_CONNECT and msg.get("first_connect"):
                        REGISTRY.sync_time(node_id)

                    self._send_ok(node_id)

                except socket.timeout:
                    REGISTRY.log(f"Timeout from device {peer_ip}", level="warning")
                    break
                except (ConnectionResetError, BrokenPipeError):
                    REGISTRY.log(f"Device {peer_ip} connection reset/closed")
                    break
                except Exception as e:
                    REGISTRY.log(f"Handler error for {peer_ip}: {e}", level="error")
                    break
        finally:
            self._cleanup(node_id, peer_ip)

    @staticmethod
    def _derive_led_state_for(node_id: str) -> str:
        """
        Map current system/node status to the contributor's LED state enums.
        States: off, mesh_connected, course_deployed, course_active,
                software_error, network_error, course_complete
        """
        # Course-based first
        cs = REGISTRY.course_status  # "Inactive" | "Deployed" | "Active"
        # Only show active/deployed if device has an action assigned
        has_action = node_id in REGISTRY.assignments
        if cs == "Active" and has_action:
            return "course_active"
        if cs == "Deployed" and has_action:
            return "course_deployed"

        # Otherwise, infer from node status (basic & safe)
        n = REGISTRY.nodes.get(node_id)
        if n:
            if n.status in ("Offline", "Unknown"):
                return "network_error"
            # If connected but no course running, treat as mesh-connected idle
            return "mesh_connected"

        # Default idle
        return "off"

    # -------------------- replies --------------------

    def _send_ok(self, node_id: str) -> None:
        n = REGISTRY.nodes.get(node_id)
        data = {
            "ack": True,
            "action": REGISTRY.assignments.get(node_id),
            "course_status": REGISTRY.course_status,
            "timestamp": utcnow_iso(),
            "master_time": REGISTRY.controller_time_ms(),
            "mesh_network": "ft_mesh",
            "server_version": VERSION,
            # NOTE: led_command removed - clients prioritize it over led_pattern
            # This was causing assigned colors to be overridden by course_active (green)
            # led_pattern is sufficient for controlling LEDs
        }
        # Converge optional state back to device if we have it
        if n:
            if n.led_pattern:
                data["led_pattern"] = n.led_pattern
            if n.audio_clip:
                data["audio_clip"] = n.audio_clip
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
    """
    Thread-per-connection server with fast shutdown.
    Allow address reuse and short socket timeouts for responsiveness.
    """
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls):
        super().__init__(server_address, handler_cls)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)
        REGISTRY.log(f"TCP server configured on {server_address}")

    def serve_forever(self, poll_interval=0.5):
        try:
            REGISTRY.log("TCP server ready for device connections")
            super().serve_forever(poll_interval=poll_interval)
        except KeyboardInterrupt:
            REGISTRY.log("TCP server interrupted, shutting down…")
            self.shutdown()


def start_heartbeat_server():
    """
    Start the heartbeat TCP server in a background thread.
    Return the server instance; main() calls .shutdown() on exit.
    """
    srv = ThreadedTCPServer((HOST, HEARTBEAT_TCP_PORT), HeartbeatHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    REGISTRY.log(f"Heartbeat listening on {HOST}:{HEARTBEAT_TCP_PORT}")
    REGISTRY.log("Ready for device connections (wlan0 mesh)")
    return srv
