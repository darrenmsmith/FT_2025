#!/usr/bin/env python3
"""
Field Trainer Core v5.2 - Enhanced Device Management and TCP Server
- Core device registry and communication logic
- Enhanced TCP heartbeat server for device connectivity
- Course management and deployment
- Improved connection handling and reliability
"""

import json
import os
import socket
import threading
import time
import subprocess
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import socketserver

# Configuration
HOST = "0.0.0.0"
HEARTBEAT_TCP_PORT = 6000
OFFLINE_SECS = 15
LOG_MAX = 1000
COURSE_FILE = "courses.json"

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_gateway_status() -> Dict[str, Any]:
    """Get comprehensive gateway status information"""
    status = {
        "mesh_active": False,
        "mesh_ssid": "Unknown",
        "mesh_cell": "Unknown", 
        "batman_neighbors": 0,
        "batman_neighbors_list": [],
        "wlan1_ssid": "Not connected",
        "wlan1_ip": "Not assigned",
        "uptime": "Unknown"
    }
    
    try:
        # Check mesh network status (wlan0)
        result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    essid = line.split('ESSID:')[1].strip().strip('"')
                    if essid != "off/any":
                        status["mesh_ssid"] = essid
                        status["mesh_active"] = True
                elif 'Cell:' in line:
                    cell = line.split('Cell:')[1].split()[0].strip()
                    status["mesh_cell"] = cell
    except Exception as e:
        print(f"iwconfig wlan0 error: {e}")
    
    try:
        # Check BATMAN neighbors - FIXED PARSING
        result = subprocess.run(['sudo', 'batctl', 'n', '-H'], capture_output=True, text=True)
        if result.returncode == 0:
            neighbors = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if line and 'wlan0' in line:
                    # Parse format: "        wlan0     b8:27:eb:5f:52:6b    0.912s"
                    parts = line.split()
                    if len(parts) >= 3:
                        # Format: [whitespace] wlan0 [mac_address] [time]
                        # Find the parts: interface, MAC, time
                        interface_idx = -1
                        for i, part in enumerate(parts):
                            if part == 'wlan0':
                                interface_idx = i
                                break
                        
                        if interface_idx != -1 and len(parts) > interface_idx + 2:
                            mac = parts[interface_idx + 1]
                            last_seen = parts[interface_idx + 2]
                            
                            # Validate MAC address format (basic check)
                            if ':' in mac and len(mac) == 17:  # MAC format: xx:xx:xx:xx:xx:xx
                                neighbors.append({
                                    "mac": mac, 
                                    "last_seen": last_seen,
                                    "interface": "wlan0"
                                })
            
            status["batman_neighbors"] = len(neighbors)
            status["batman_neighbors_list"] = neighbors
            
            # Debug logging
            print(f"BATMAN Debug: Found {len(neighbors)} neighbors")
            for neighbor in neighbors:
                print(f"  - {neighbor['mac']} (last seen: {neighbor['last_seen']})")
                
    except Exception as e:
        print(f"BATMAN neighbor detection error: {e}")
        # Also log the raw output for debugging
        try:
            result = subprocess.run(['sudo', 'batctl', 'n', '-H'], capture_output=True, text=True)
            print(f"BATMAN raw output: {repr(result.stdout)}")
        except:
            pass
    
    try:
        # Check wlan1 connection status
        result = subprocess.run(['iwconfig', 'wlan1'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    essid = line.split('ESSID:')[1].strip().strip('"')
                    if essid != "off/any":
                        status["wlan1_ssid"] = essid
        
        # Get wlan1 IP address
        result = subprocess.run(['ip', 'addr', 'show', 'wlan1'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and 'scope global' in line:
                    ip = line.strip().split()[1].split('/')[0]
                    status["wlan1_ip"] = ip
    except Exception as e:
        print(f"wlan1 status error: {e}")
    
    try:
        # Get system uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            status["uptime"] = f"{hours}h {minutes}m"
    except Exception as e:
        print(f"Uptime error: {e}")
    
    return status

def load_courses() -> Dict[str, Any]:
    if os.path.exists(COURSE_FILE):
        with open(COURSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "courses": [
            {
                "name": "Course A",
                "description": "6-station circuit training loop",
                "stations": [
                    {"node_id": "192.168.99.100", "action": "lunge", "instruction": "Welcome! Do 10 lunges, then sprint to Device 1"},
                    {"node_id": "192.168.99.101", "action": "sprint", "instruction": "Sprint to Device 2", "distance_yards": 40},
                    {"node_id": "192.168.99.102", "action": "jog", "instruction": "Jog to Device 3", "distance_yards": 30},
                    {"node_id": "192.168.99.103", "action": "backpedal", "instruction": "Backpedal to Device 4", "distance_yards": 25},
                    {"node_id": "192.168.99.104", "action": "carioca", "instruction": "Carioca to Device 5", "distance_yards": 20},
                    {"node_id": "192.168.99.105", "action": "high_knees", "instruction": "High knees back to start", "distance_yards": 30}
                ]
            },
            {
                "name": "Course B",
                "description": "Strength circuit with Device 0",
                "stations": [
                    {"node_id": "192.168.99.100", "action": "welcome", "instruction": "Welcome! Move to Device 1"},
                    {"node_id": "192.168.99.101", "action": "pushups", "instruction": "10 pushups, then move to Device 2", "reps": 10},
                    {"node_id": "192.168.99.102", "action": "situps", "instruction": "15 situps, then return to start", "reps": 15}
                ]
            }
        ]
    }

@dataclass
class NodeInfo:
    node_id: str
    ip: str
    status: str = "Unknown"
    action: Optional[str] = None
    ping_ms: Optional[int] = None
    hops: Optional[int] = None
    last_msg: Optional[str] = None
    sensors: Dict[str, Any] = field(default_factory=dict)
    accelerometer_working: bool = False
    audio_working: bool = False  
    battery_level: Optional[float] = None
    _writer: Any = field(default=None, repr=False, compare=False)

class Registry:
    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self.nodes_lock = threading.Lock()
        self.logs: deque = deque(maxlen=LOG_MAX)
        self.course_status: str = "Inactive"
        self.selected_course: Optional[str] = None
        self.courses = load_courses()
        self.assignments: Dict[str, str] = {}  # {node_id: action}
        # Track Device 0 as a virtual node for the circuit
        self.device_0_action: Optional[str] = None

    def log(self, msg: str, level: str = "info", source: str = "controller", node_id: Optional[str] = None):
        entry = {"ts": utcnow_iso(), "level": level, "source": source, "node_id": node_id, "msg": msg}
        self.logs.appendleft(entry)
        print(f"[{entry['ts']}] {level.upper()}: {msg}")

    def upsert_node(self, node_id: str, ip: str, writer=None, **fields):
        with self.nodes_lock:
            n = self.nodes.get(node_id)
            if n is None:
                n = NodeInfo(node_id=node_id, ip=ip)
                self.nodes[node_id] = n
                self.log(f"Device {node_id} connected")
            
            # Update fields safely - handle both 'role' and 'action' for backwards compatibility
            for k, v in fields.items():
                if k == 'role' and hasattr(n, 'action'):
                    n.action = v  # Map old 'role' to new 'action'
                elif hasattr(n, k) and k != '_writer':
                    setattr(n, k, v)
            
            n.last_msg = utcnow_iso()
            if writer is not None:
                n._writer = writer

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        with self.nodes_lock:
            nodes_list = []
            
            # Add Device 0 (controller) as a virtual node
            device_0_status = "Active" if self.course_status == "Active" else "Standby"
            if self.course_status != "Inactive":
                device_0_node = {
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
                    "battery_level": None
                }
                nodes_list.append(device_0_node)
            
            # Add connected client devices
            for n in self.nodes.values():
                # Calculate offline status
                derived_status = n.status
                if n.last_msg:
                    try:
                        last_ts = datetime.fromisoformat(n.last_msg).timestamp()
                        if now - last_ts > OFFLINE_SECS and n.status != "Unknown":
                            derived_status = "Offline"
                    except Exception:
                        pass
                
                # Create serializable dictionary manually (avoid socket serialization issues)
                node_data = {
                    "node_id": n.node_id,
                    "ip": n.ip, 
                    "status": derived_status,
                    "action": n.action,
                    "ping_ms": n.ping_ms,
                    "hops": n.hops,
                    "last_msg": n.last_msg,
                    "sensors": n.sensors or {},
                    "accelerometer_working": n.accelerometer_working,
                    "audio_working": n.audio_working,
                    "battery_level": n.battery_level
                }
                nodes_list.append(node_data)
        
        # Sort by node_id for consistent display
        nodes_list.sort(key=lambda x: x.get("node_id", ""))
        
        return {
            "course_status": self.course_status,
            "selected_course": self.selected_course,
            "nodes": nodes_list,
            "gateway_status": get_gateway_status()
        }

    def send_to_node(self, node_id: str, payload: Dict[str, Any]) -> bool:
        """Enhanced send method with better error handling"""
        # Handle Device 0 (controller/gateway) specially
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
                
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                self.log(f"Send failed to Device {node_id}: {e}", level="error")
                # Mark device as disconnected
                n._writer = None
                n.status = "Offline"
                return False
            except Exception as e:
                self.log(f"Unexpected error sending to Device {node_id}: {e}", level="error")
                return False

    def deploy_course(self, course_name: str) -> Dict[str, Any]:
        """Deploy a course to devices"""
        try:
            course = next((c for c in self.courses.get("courses", []) if c.get("name") == course_name), None)
            if not course:
                return {"success": False, "error": "Course not found"}

            # First, clear all existing assignments and reset devices to standby
            self.log("Clearing previous course assignments")
            old_assignments = self.assignments.copy()
            
            # Send stop command to all previously assigned devices
            for node_id in old_assignments.keys():
                if node_id != "192.168.99.100":  # Skip Device 0
                    self.send_to_node(node_id, {"cmd": "stop", "action": None})
            
            # Clear actions from all devices in memory
            with self.nodes_lock:
                for node in self.nodes.values():
                    node.action = None
            
            self.device_0_action = None
            self.assignments.clear()

            # Now deploy the new course
            self.selected_course = course_name
            self.course_status = "Deployed"
            self.assignments = {st["node_id"]: st["action"] for st in course.get("stations", [])}
            
            # Set Device 0 action
            device_0_station = next((st for st in course.get("stations", []) if st["node_id"] == "192.168.99.100"), None)
            if device_0_station:
                self.device_0_action = device_0_station["action"]
            
            self.log(f"Deployed course '{course_name}' with {len(self.assignments)} stations")
            
            # Send deployment to connected devices (skip Device 0)
            success_count = 0
            for node_id, action in self.assignments.items():
                if node_id != "192.168.99.100":  # Skip Device 0
                    deploy_msg = {"deploy": True, "action": action, "course": course_name}
                    if self.send_to_node(node_id, deploy_msg):
                        success_count += 1

            # Send "inactive" status to devices NOT in this course
            with self.nodes_lock:
                for node_id in self.nodes.keys():
                    if node_id not in self.assignments and node_id != "192.168.99.100":
                        inactive_msg = {"deploy": True, "action": None, "course": course_name, "status": "inactive"}
                        self.send_to_node(node_id, inactive_msg)
                        self.log(f"Set {node_id} to inactive (not in course)")
                        
            self.log(f"Deployment sent to {success_count}/{len(self.assignments)-1} client devices")
            self.log(f"Devices not in course returned to standby")
            return {"success": True, "course_status": self.course_status, "deployed_to": success_count}
            
        except Exception as e:
            self.log(f"Deploy error: {e}", level="error")
            return {"success": False, "error": "Deployment failed"}

    def activate_course(self, course_name: Optional[str] = None) -> Dict[str, Any]:
        """Activate the deployed course"""
        try:
            course_name = course_name or self.selected_course
            
            if not course_name:
                return {"success": False, "error": "No course selected"}
                
            self.course_status = "Active"
            self.log(f"Activated course '{course_name}' - Circuit training ready")
            
            # Send activation to assigned devices (Device 0 doesn't need TCP activation)
            success_count = 0
            for node_id in self.assignments.keys():
                if node_id != "192.168.99.100":  # Skip Device 0
                    if self.send_to_node(node_id, {"cmd": "start"}):
                        success_count += 1
            
            self.log(f"Activation sent to {success_count}/{len(self.assignments)-1} client devices")
            return {"success": True, "course_status": self.course_status}
            
        except Exception as e:
            self.log(f"Activate error: {e}", level="error")
            return {"success": False, "error": "Activation failed"}

    def deactivate_course(self) -> Dict[str, Any]:
        """Deactivate the current course"""
        try:
            self.log("Deactivating course")
            
            # Send stop command to all assigned devices (except Device 0)
            for node_id in list(self.assignments.keys()):
                if node_id != "192.168.99.100":
                    self.send_to_node(node_id, {"cmd": "stop"})
            
            # Reset state
            self.course_status = "Inactive"
            self.selected_course = None
            self.assignments.clear()
            self.device_0_action = None
            
            # Clear device actions
            with self.nodes_lock:
                for node in self.nodes.values():
                    node.action = None
            
            self.log("Course deactivated - all devices returned to standby")
            return {"success": True, "course_status": self.course_status}
            
        except Exception as e:
            self.log(f"Deactivate error: {e}", level="error")
            return {"success": False, "error": "Deactivation failed"}

    def clear_logs(self):
        """Clear system logs"""
        self.logs.clear()
        self.log("System logs cleared by user")

# Global registry instance
REGISTRY = Registry()

# Enhanced TCP Heartbeat Server
class HeartbeatHandler(socketserver.StreamRequestHandler):
    """Enhanced heartbeat handler with better connection management"""
    
    def setup(self):
        """Configure socket when connection is established"""
        # Enable TCP keep-alive for reliable connection detection
        self.request.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Configure keep-alive timing (Linux/Raspberry Pi)
        try:
            # Send keep-alive after 30 seconds of inactivity
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            # Send keep-alive probes every 5 seconds
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
            # Declare connection dead after 3 failed probes
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except (OSError, AttributeError):
            # Keep-alive parameters not available on this platform
            pass
        
        # Set read timeout to detect unresponsive clients
        self.request.settimeout(45.0)  # 45 second timeout
        
        super().setup()

    def handle(self):
        peer_ip = self.client_address[0]
        node_id = None
        
        REGISTRY.log(f"Device connected from {peer_ip}")
        
        try:
            while True:
                try:
                    # Read incoming heartbeat message
                    line = self.rfile.readline()
                    if not line:
                        REGISTRY.log(f"Device {peer_ip} closed connection cleanly")
                        break
                    
                    # Parse JSON message
                    try:
                        msg = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError as e:
                        REGISTRY.log(f"Invalid JSON from {peer_ip}: {e}", level="error")
                        # Send error response and continue
                        self._send_error_response("Invalid JSON format")
                        continue
                    
                    node_id = msg.get("node_id") or peer_ip
                    
                    # Update node registry with received data
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
                        action=msg.get("action")
                    )
                    
                    # Build and send reply
                    reply = self._build_reply(node_id)
                    self._send_response(reply)
                    
                except socket.timeout:
                    REGISTRY.log(f"Timeout from device {peer_ip} - connection may be dead", level="warning")
                    break
                except ConnectionResetError:
                    REGISTRY.log(f"Device {peer_ip} reset connection")
                    break
                except BrokenPipeError:
                    REGISTRY.log(f"Broken pipe to device {peer_ip}")
                    break
                except Exception as e:
                    REGISTRY.log(f"Handler error for {peer_ip}: {e}", level="error")
                    break
                    
        finally:
            # Always clean up connection
            self._cleanup_connection(node_id, peer_ip)

    def _build_reply(self, node_id: str) -> Dict[str, Any]:
        """Build reply message with current course assignments"""
        assigned_action = REGISTRY.assignments.get(node_id)
        
        return {
            "ack": True,
            "action": assigned_action,
            "course_status": REGISTRY.course_status,
            "timestamp": utcnow_iso(),
            "mesh_network": "smithhome"  # Your mesh network identifier
        }

    def _send_response(self, data: Dict[str, Any]):
        """Send JSON response to device with error handling"""
        try:
            response_data = (json.dumps(data) + "\n").encode("utf-8")
            self.wfile.write(response_data)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            REGISTRY.log(f"Failed to send response to device: {e}", level="error")
            raise  # Re-raise to trigger connection cleanup

    def _send_error_response(self, error_msg: str):
        """Send error response to device"""
        try:
            error_data = {"error": error_msg, "timestamp": utcnow_iso()}
            self._send_response(error_data)
        except Exception:
            pass  # Don't log errors for error responses

    def _cleanup_connection(self, node_id: Optional[str], peer_ip: str):
        """Clean up when device disconnects"""
        if node_id:
            REGISTRY.log(f"Device {node_id} ({peer_ip}) disconnected")
            # Mark device as disconnected
            with REGISTRY.nodes_lock:
                if node_id in REGISTRY.nodes:
                    REGISTRY.nodes[node_id]._writer = None
        else:
            REGISTRY.log(f"Unknown device {peer_ip} disconnected")


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    """Enhanced TCP server optimized for field device connections"""
    
    allow_reuse_address = True
    daemon_threads = True  # Threads die when main thread dies
    
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        
        # Configure server socket for reliability
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Set reasonable timeout for accept operations
        self.socket.settimeout(1.0)
        
        REGISTRY.log(f"TCP server configured for mesh network on {server_address}")

    def serve_forever(self, poll_interval=0.5):
        """Enhanced serve_forever with better shutdown handling"""
        try:
            REGISTRY.log("TCP server ready for device connections")
            super().serve_forever(poll_interval)
        except KeyboardInterrupt:
            REGISTRY.log("TCP server shutting down...")
            self.shutdown()


def start_heartbeat_server():
    """Start enhanced TCP heartbeat server"""
    try:
        srv = ThreadedTCPServer((HOST, HEARTBEAT_TCP_PORT), HeartbeatHandler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        REGISTRY.log(f"Enhanced TCP heartbeat server started on {HOST}:{HEARTBEAT_TCP_PORT}")
        REGISTRY.log("Ready for Device 1-5 connections via wlan0 mesh")
        return srv
    except OSError as e:
        REGISTRY.log(f"Failed to start TCP server on port {HEARTBEAT_TCP_PORT}: {e}", level="error")
        raise


def start_connection_monitor():
    """Optional: Monitor device connections every 30 seconds"""
    def monitor_connections():
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            with REGISTRY.nodes_lock:
                active_devices = [node_id for node_id, node in REGISTRY.nodes.items() 
                                if node._writer is not None]
                offline_devices = [node_id for node_id, node in REGISTRY.nodes.items() 
                                 if node._writer is None and node.status != "Unknown"]
            
            if active_devices or offline_devices:
                REGISTRY.log(f"Connection status - Active: {len(active_devices)}, Offline: {len(offline_devices)}")
                if offline_devices:
                    REGISTRY.log(f"Offline devices: {', '.join(offline_devices)}", level="warning")
    
    monitor_thread = threading.Thread(target=monitor_connections, daemon=True)
    monitor_thread.start()
    REGISTRY.log("Connection monitoring started")


if __name__ == "__main__":
    # Run as standalone TCP server
    start_heartbeat_server()
    
    # Optionally start connection monitoring
    start_connection_monitor()
    
    REGISTRY.log("Field Trainer Core v5.2 Enhanced TCP server running")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        REGISTRY.log("Shutting down...")
