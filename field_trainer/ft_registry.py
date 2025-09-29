"""
Registry orchestrates:
- node state (connected devices)
- system logs
- course assign/deploy/activate/deactivate
- snapshot() for the web API

It delegates mesh status to ft_mesh.get_gateway_status().
"""

import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, List

from .ft_config import LOG_MAX, OFFLINE_SECS
from .ft_courses import load_courses
from .ft_mesh import get_gateway_status
from .ft_models import NodeInfo, utcnow_iso
from .ft_version import VERSION


class Registry:
    """Thread-safe registry for devices + course lifecycle."""

    def __init__(self) -> None:
        self.nodes: Dict[str, NodeInfo] = {}
        self.nodes_lock = threading.Lock()
        self.logs: deque = deque(maxlen=LOG_MAX)
        self.course_status: str = "Inactive"
        self.selected_course: Optional[str] = None
        self.courses = load_courses()
        self.assignments: Dict[str, str] = {}  # node_id -> action
        self.device_0_action: Optional[str] = None  # virtual Device 0

    # ----------------- Logging -----------------

    def log(self, msg: str, level: str = "info", source: str = "controller", node_id: Optional[str] = None) -> None:
        """Append a structured log entry and print to stdout for operators."""
        entry = {"ts": utcnow_iso(), "level": level, "source": source, "node_id": node_id, "msg": msg}
        self.logs.appendleft(entry)
        print(f"[{entry['ts']}] {level.upper()}: {msg}")

    # ----------------- Device state -----------------

    def upsert_node(self, node_id: str, ip: str, writer=None, **fields) -> None:
        """
        Create or update a device record.

        - writer: a socket stream (not serialized) to reply to the device
        - Backwards-compat: map incoming 'role' to 'action' if present.
        """
        with self.nodes_lock:
            n = self.nodes.get(node_id)
            if n is None:
                n = NodeInfo(node_id=node_id, ip=ip)
                self.nodes[node_id] = n
                self.log(f"Device {node_id} connected")

            for k, v in fields.items():
                if k == "role" and hasattr(n, "action"):
                    n.action = v
                elif hasattr(n, k) and k != "_writer":
                    setattr(n, k, v)

            n.last_msg = utcnow_iso()
            if writer is not None:
                n._writer = writer

    # ----------------- Snapshot for API -----------------

    def snapshot(self) -> Dict[str, Any]:
        """Current system picture consumed by the web UI."""
        now = time.time()
        nodes_list: List[Dict[str, Any]] = []

        # Virtual Device 0 (controller/gateway) appears only when not Inactive
        device_0_status = "Active" if self.course_status == "Active" else "Standby"
        if self.course_status != "Inactive":
            nodes_list.append({
                "node_id": "192.168.99.100",
                "ip": "192.168.99.100",
                "status": device_0_status,
                "action": self.device_0_action,
                "ping_ms": 0,
                "hops": 0,
                "last_msg": utcnow_iso(),
                "sensors": {},
                "accelerometer_working": True,
                "audio_working": True,
                "battery_level": None,
            })

        with self.nodes_lock:
            for n in self.nodes.values():
                derived = n.status
                # Infer offline if last_msg is too old and device isn't Unknown
                if n.last_msg:
                    try:
                        last_ts = datetime.fromisoformat(n.last_msg).timestamp()
                        if now - last_ts > OFFLINE_SECS and n.status != "Unknown":
                            derived = "Offline"
                    except Exception:
                        pass

                nodes_list.append({
                    "node_id": n.node_id,
                    "ip": n.ip,
                    "status": derived,
                    "action": n.action,
                    "ping_ms": n.ping_ms,
                    "hops": n.hops,
                    "last_msg": n.last_msg,
                    "sensors": n.sensors or {},
                    "accelerometer_working": n.accelerometer_working,
                    "audio_working": n.audio_working,
                    "battery_level": n.battery_level,
                })

        nodes_list.sort(key=lambda x: x.get("node_id", ""))

        return {
            "course_status": self.course_status,
            "selected_course": self.selected_course,
            "nodes": nodes_list,
            "gateway_status": get_gateway_status(),  # mesh + wifi probing
            "version": VERSION,
        }

    # ----------------- Device messaging -----------------

    def send_to_node(self, node_id: str, payload: Dict[str, Any]) -> bool:
        """
        Send a JSON command to a connected device.

        Device 0 is virtual: we only log its assignments instead of sending.
        """
        if node_id == "192.168.99.100":
            self.log(f"Device 0 (Gateway) assigned action: {payload.get('action', payload.get('role', 'Unknown'))}")
            return True

        with self.nodes_lock:
            n = self.nodes.get(node_id)
            if not n or not n._writer:
                self.log(f"Cannot send to Device {node_id}: not connected", level="error")
                return False
            try:
                data = (json.dumps(payload) + "\n").encode("utf-8")
                n._writer.write(data)
                n._writer.flush()
                self.log(f"Sent to Device {node_id}: {payload}")
                return True
            except Exception as e:
                self.log(f"Send failed to Device {node_id}: {e}", level="error")
                n._writer = None
                n.status = "Offline"
                return False

    # ----------------- Course lifecycle -----------------

    def deploy_course(self, course_name: str) -> Dict[str, Any]:
        """Assign actions to nodes per course definition and notify clients."""
        try:
            course = next((c for c in self.courses.get("courses", []) if c.get("name") == course_name), None)
            if not course:
                return {"success": False, "error": "Course not found"}

            # Clear existing
            self.log("Clearing previous course assignments")
            old_assignments = self.assignments.copy()
            for node_id in old_assignments.keys():
                if node_id != "192.168.99.100":
                    self.send_to_node(node_id, {"cmd": "stop", "action": None})

            with self.nodes_lock:
                for node in self.nodes.values():
                    node.action = None
            self.device_0_action = None
            self.assignments.clear()

            # Deploy new course
            self.selected_course = course_name
            self.course_status = "Deployed"
            self.assignments = {st["node_id"]: st["action"] for st in course.get("stations", [])}

            # Device 0 (virtual) action
            d0 = next((st for st in course.get("stations", []) if st["node_id"] == "192.168.99.100"), None)
            if d0:
                self.device_0_action = d0["action"]

            self.log(f"Deployed course '{course_name}' with {len(self.assignments)} stations")

            # Notify connected devices (skip Device 0)
            success = 0
            for node_id, action in self.assignments.items():
                if node_id != "192.168.99.100":
                    if self.send_to_node(node_id, {"deploy": True, "action": action, "course": course_name}):
                        success += 1

            # Mark unassigned nodes inactive
            with self.nodes_lock:
                for node_id in self.nodes.keys():
                    if node_id not in self.assignments and node_id != "192.168.99.100":
                        self.send_to_node(node_id, {"deploy": True, "action": None, "course": course_name, "status": "inactive"})
                        self.log(f"Set {node_id} to inactive (not in course)")

            self.log(f"Deployment sent to {success}/{max(0, len(self.assignments)-1)} client devices")
            return {"success": True, "course_status": self.course_status, "deployed_to": success}
        except Exception as e:
            self.log(f"Deploy error: {e}", level="error")
            return {"success": False, "error": "Deployment failed"}

    def activate_course(self, course_name: Optional[str] = None) -> Dict[str, Any]:
        """Start the deployed course."""
        try:
            course_name = course_name or self.selected_course
            if not course_name:
                return {"success": False, "error": "No course selected"}

            self.course_status = "Active"
            self.log(f"Activated course '{course_name}' - Circuit training ready")

            success = 0
            for node_id in self.assignments.keys():
                if node_id != "192.168.99.100":
                    if self.send_to_node(node_id, {"cmd": "start"}):
                        success += 1

            self.log(f"Activation sent to {success}/{max(0, len(self.assignments)-1)} client devices")
            return {"success": True, "course_status": self.course_status}
        except Exception as e:
            self.log(f"Activate error: {e}", level="error")
            return {"success": False, "error": "Activation failed"}

    def deactivate_course(self) -> Dict[str, Any]:
        """Stop course and reset all devices to standby."""
        try:
            self.log("Deactivating course")
            for node_id in list(self.assignments.keys()):
                if node_id != "192.168.99.100":
                    self.send_to_node(node_id, {"cmd": "stop"})

            self.course_status = "Inactive"
            self.selected_course = None
            self.assignments.clear()
            self.device_0_action = None

            with self.nodes_lock:
                for node in self.nodes.values():
                    node.action = None

            self.log("Course deactivated - all devices returned to standby")
            return {"success": True, "course_status": self.course_status}
        except Exception as e:
            self.log(f"Deactivate error: {e}", level="error")
            return {"success": False, "error": "Deactivation failed"}

    # ----------------- Logs -----------------

    def clear_logs(self) -> None:
        self.logs.clear()
        self.log("System logs cleared by user")


# Global singleton registry (same name as before for compatibility)
REGISTRY = Registry()
