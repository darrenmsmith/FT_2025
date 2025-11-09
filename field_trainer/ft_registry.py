"""
Registry: the system's in-memory state + operations.
- Tracks nodes, logs, course status, assignments
- Provides snapshot() for the UI
- Sends commands to devices
- Optional server LED (Device 0) control and shutdown
"""

import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from .ft_config import (
    LOG_MAX, OFFLINE_SECS,
    ENABLE_SERVER_LED, SERVER_LED_PIN, SERVER_LED_COUNT, SERVER_LED_BRIGHTNESS
)
from .ft_courses import load_courses
from .ft_mesh import get_gateway_status
from .ft_models import NodeInfo, utcnow_iso
from .ft_version import VERSION
from .ft_led import LEDManager, LEDState
from .ft_config import (
    LOG_MAX, OFFLINE_SECS,
    ENABLE_SERVER_LED, SERVER_LED_PIN, SERVER_LED_COUNT, SERVER_LED_BRIGHTNESS,
    ENABLE_SERVER_AUDIO, AUDIO_DIR, AUDIO_CONFIG_PATH, AUDIO_VOICE_GENDER, AUDIO_VOLUME_PERCENT
)
from .ft_audio import AudioManager, AudioSettings



class Registry:
    """Thread-safe registry for devices + course lifecycle."""

    def __init__(self) -> None:

        # Node storage + lock
        self.nodes: Dict[str, NodeInfo] = {}
        self.nodes_lock = threading.Lock()

        # System log
        self.logs: deque = deque(maxlen=LOG_MAX)

        # Course state
        self.course_status: str = "Inactive"
        self.selected_course: Optional[str] = None

        # courses loaded after DB init below
        self.assignments: Dict[str, str] = {}  # node_id -> action
        self.device_0_action: Optional[str] = None  # virtual Device 0 state marker

        # Optional server-side LED control (Device 0 hardware)
        self._server_led: Optional[LEDManager] = None
        if ENABLE_SERVER_LED:
            try:
                self._server_led = LEDManager(
                    pin=SERVER_LED_PIN, led_count=SERVER_LED_COUNT, brightness=SERVER_LED_BRIGHTNESS
                )
                self.log("Server LED manager initialized")
            except Exception as e:
                self.log(f"Server LED init failed: {e}", level="error")

        # Optional server-side Audio (Device 0 loudspeaker via mpg123)
        self._audio: Optional[AudioManager] = None
        if ENABLE_SERVER_AUDIO:
            try:
                aset = AudioSettings(
                    audio_dir=AUDIO_DIR,
                    voice_gender=AUDIO_VOICE_GENDER,
                    volume_percent=AUDIO_VOLUME_PERCENT,
                    config_path=AUDIO_CONFIG_PATH,
                )
                self._audio = AudioManager(settings=aset)
                self.log(f"Server Audio manager initialized (dir={aset.audio_dir}, gender={aset.voice_gender}, vol={aset.volume_percent}%)")
            except Exception as e:
                self.log(f"Server Audio init failed: {e}", level="error")

        # Database integration (Phase 1)
        try:
            from .db_manager import DatabaseManager
            self.db = DatabaseManager('/opt/data/field_trainer.db')
            self.log("Database manager initialized")
        except Exception as e:
            self.log(f"Database init failed: {e}", level="error")
            self.db = None
        
        # Load courses from database (after DB init)
        self.courses = self._load_courses_from_db() if self.db else load_courses()
        
        # Touch event handler (set by coach_interface)
        self._touch_handler = None

    def _load_courses_from_db(self) -> Dict[str, Any]:
        """Load courses from database in JSON-compatible format for deployment"""
        try:
            courses_list = []
            
            for course_row in self.db.get_all_courses():
                course = self.db.get_course(course_row['course_id'])
                
                # Convert to old JSON format for compatibility with deploy_course()
                stations = []
                for action in course['actions']:
                    stations.append({
                        "node_id": action['device_id'],
                        "action": action['action'],
                        "instruction": action.get('instruction', '')
                    })
                
                courses_list.append({
                    "name": course['course_name'],
                    "description": course.get('description', ''),
                    "stations": stations
                })
            
            self.log(f"Loaded {len(courses_list)} courses from database")
            return {"courses": courses_list}
            
        except Exception as e:
            self.log(f"Failed to load courses from database: {e}", level="error")
            return {"courses": []}

    def reload_courses(self) -> bool:
        """Reload courses from database (call after creating/editing courses)"""
        try:
            self.courses = self._load_courses_from_db() if self.db else load_courses()
            self.log(f"Courses reloaded - {len(self.courses.get('courses', []))} courses available")
            return True
        except Exception as e:
            self.log(f"Failed to reload courses: {e}", level="error")
            return False

	# ---------------- Utilities ----------------

    def log(self, msg: str, level: str = "info", source: str = "controller", node_id: Optional[str] = None) -> None:
        """Append a structured log entry and also print for operator visibility."""
        entry = {"ts": utcnow_iso(), "level": level, "source": source, "node_id": node_id, "msg": msg}
        self.logs.appendleft(entry)
        print(f"[{entry['ts']}] {level.upper()}: {msg}")

    @staticmethod
    def controller_time_ms() -> int:
        """Controller UTC timestamp in milliseconds."""
        import time as _t
        return int(_t.time() * 1000)

    # ---------------- Device State ----------------

    def upsert_node(self, node_id: str, ip: str, writer=None, **fields) -> None:
        """
        Create or update a device record:
          - Sets/updates all allowed NodeInfo fields
          - Maintains last_msg timestamp
          - Stores socket writer for replies
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

        # Handle touch events (Phase 1)
            if fields.get('touch_detected'):
                touch_timestamp = fields.get('touch_timestamp', time.time())

                # Handle asynchronously to not block heartbeat
                threading.Thread(
                    target=self.handle_touch_event,
                    args=(node_id, touch_timestamp),
                    daemon=True
                ).start()

    # ---------------- Snapshot for UI ----------------

    def snapshot(self) -> Dict[str, Any]:
        """
        Return the current system state consumed by the UI.
        Note: Provides a virtual Device 0 when course is not Inactive.
        """
        now = time.time()
        nodes_list: List[Dict[str, Any]] = []

        # Virtual Device 0 (controller/gateway)
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
            "gateway_status": get_gateway_status(),  # live mesh/wifi probe
            "version": VERSION,
        }

    # ---------------- Device Commands ----------------

    def send_to_node(self, node_id: str, payload: Dict[str, Any]) -> bool:
        """
        Send a JSON command to a connected device.
        - Device 0 is virtual: only logs and updates state.
        """
        print(f"\n📤 SEND_TO_NODE: {node_id}")
        print(f"   Command: {payload.get('cmd', payload.get('deploy', 'unknown'))}")
        print(f"   Full payload: {payload}")

        if node_id == "192.168.99.100":
            self.log(f"Device 0 virtual command: {payload}")
            print(f"   ℹ️  Device 0 is virtual - no actual send")
            return True

        with self.nodes_lock:
            n = self.nodes.get(node_id)
            if not n or not n._writer:
                self.log(f"Cannot send to Device {node_id}: not connected", level="error")
                print(f"   ❌ Device not connected or no writer")
                return False
            try:
                data = (json.dumps(payload) + "\n").encode("utf-8")
                n._writer.write(data)
                n._writer.flush()
                self.log(f"Sent to Device {node_id}: {payload}")
                print(f"   ✅ Sent successfully")
                return True
            except Exception as e:
                self.log(f"Send failed to Device {node_id}: {e}", level="error")
                print(f"   ❌ Send failed: {e}")
                n._writer = None
                n.status = "Offline"
                return False

    # ---- LED / Audio / Time (public API; safe even if devices ignore) ----

    def set_led(self, node_id: str, pattern: str) -> bool:
        """
        Update LED pattern on a device.
        For Device 0, also drive the optional server LED (if enabled on this host).
        Known patterns: off, solid_green, solid_red, solid_amber, rainbow
        """
        if node_id == "192.168.99.100":
            if self._server_led:
                mapping = {
                    "off": LEDState.OFF,
                    "solid_green": LEDState.SOLID_GREEN,
                    "solid_red": LEDState.SOLID_RED,
                    "solid_blue": LEDState.SOLID_BLUE,
                    "solid_amber": LEDState.SOLID_ORANGE,
                    "blink_amber": LEDState.BLINK_ORANGE,
                    "rainbow": LEDState.RAINBOW,
                }
                self._server_led.set_state(mapping.get(pattern, LEDState.OFF))
            self.device_0_action = f"LED:{pattern}"
            self.log(f"Device 0 LED set -> {pattern}")
            return True

        ok = self.send_to_node(node_id, {"cmd": "led", "pattern": pattern})
        if ok:
            with self.nodes_lock:
                if node_id in self.nodes:
                    self.nodes[node_id].led_pattern = pattern
        return ok

    def play_audio(self, node_id: str, clip: str) -> bool:
        """
        Ask a device to play a logical clip identifier (device maps to actual file).
        - For Device 0 (controller), play locally via mpg123 if ENABLE_SERVER_AUDIO=1.
        - For other devices, send a wire command; they decide how to play it.
        """
        print(f"\n🔊 PLAY_AUDIO CALLED")
        print(f"   Device: {node_id}")
        print(f"   Clip: {clip}")
        print(f"   Audio manager available: {self._audio is not None}")
    
        if node_id == "192.168.99.100":
            ok = True
            if self._audio:
                print(f"   Playing locally via AudioManager...")
                ok = self._audio.play(clip)
                if not ok:
                    self.log(f"Device 0 AUDIO failed (clip='{clip}')", level="error")
                    print(f"   ❌ AudioManager.play() returned False")
                else:
                    print(f"   ✅ AudioManager.play() succeeded")
            else:
                 print(f"   ⚠️  No AudioManager - audio disabled")
            # Always reflect the intent in UI even if playback failed (so user sees the command)
            self.device_0_action = f"AUDIO:{clip}"
            self.log(f"Device 0 AUDIO -> {clip} (played={ok})")
            return ok

        print(f"   Sending audio command to remote device...")
        ok = self.send_to_node(node_id, {"cmd": "audio", "clip": clip})
        if ok:
           with self.nodes_lock:
               if node_id in self.nodes:
                   self.nodes[node_id].audio_clip = clip
           print(f"   ✅ Audio command sent to device")
        else:
             print(f"   ❌ Failed to send audio command")
        return ok

    # ---------------- Course Lifecycle ----------------

    def deploy_course(self, course_name: str) -> Dict[str, Any]:
        """Assign actions to nodes per course definition and notify clients."""
        print("\n" + "="*80)
        print(f"🚀 DEPLOY_COURSE CALLED: {course_name}")
        print("="*80)        
        try:
            course = next((c for c in self.courses.get("courses", []) if c.get("name") == course_name), None)
            if not course:
                return {"success": False, "error": "Course not found"}

            # Stop previous
            self.log("Clearing previous course assignments")
            old_assignments = self.assignments.copy()
            for node_id in old_assignments.keys():
                if node_id != "192.168.99.100":
                    self.send_to_node(node_id, {"cmd": "stop", "action": None})

            # Reset local state
            with self.nodes_lock:
                for node in self.nodes.values():
                    node.action = None
            self.device_0_action = None
            self.assignments.clear()

            # Deploy
            self.selected_course = course_name
            self.course_status = "Deployed"
            # Update server LED to red (deployed)
            if self._server_led:
                from .ft_led import LEDState
                self._server_led.set_state(LEDState.SOLID_RED)
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

            # Mark unassigned devices as inactive
            # DISABLED: This can cause TCP blocking on partial deployments
            # TODO: Make this async or add proper timeout handling
            # with self.nodes_lock:
            #     for node_id in self.nodes.keys():
            #         if node_id not in self.assignments and node_id != "192.168.99.100":
            #             self.send_to_node(node_id, {"deploy": True, "action": None, "course": course_name, "status": "inactive"})
            #             self.log(f"Set {node_id} to inactive (not in course)")

            self.log(f"Deployment sent to {success}/{max(0, len(self.assignments)-1)} client devices")
            print(f"📊 DEPLOY SUMMARY:")
            print(f"   Course: {course_name}")
            print(f"   Devices assigned: {len(self.assignments)}")
            print(f"   Successfully notified: {success}")
            print(f"   Course status: {self.course_status}")
            print("="*80 + "\n")            

            return {"success": True, "course_status": self.course_status, "deployed_to": success}

        except Exception as e:
            self.log(f"Deploy error: {e}", level="error")
            return {"success": False, "error": "Deployment failed"}

    def activate_course(self, course_name: Optional[str] = None) -> Dict[str, Any]:
        """Start the deployed course."""
        print("\n" + "="*80)
        print(f"🟢 ACTIVATE_COURSE CALLED")
        print(f"   Course name param: {course_name}")
        print(f"   Selected course: {self.selected_course}")
        print(f"   Current status: {self.course_status}")
        print(f"   Assignments: {len(self.assignments)} devices")
        print("="*80)
        try:
            course_name = course_name or self.selected_course
            if not course_name:

                return {"success": False, "error": "No course selected"}

            self.course_status = "Active"
            # Update server LED to green (active)
            if self._server_led:
                from .ft_led import LEDState
                self._server_led.set_state(LEDState.SOLID_GREEN)
            self.log(f"Activated course '{course_name}' - Circuit training ready")

            success = 0
            for node_id in self.assignments.keys():
                if node_id != "192.168.99.100":
                    if self.send_to_node(node_id, {"cmd": "start", "course_status": "Active"}):
                        success += 1

            self.log(f"Activation sent to {success}/{max(0, len(self.assignments)-1)} client devices")
            print(f"📊 ACTIVATION SUMMARY:")
            print(f"   Course: {course_name}")
            print(f"   New status: {self.course_status}")
            print(f"   Devices activated: {success}/{max(0, len(self.assignments)-1)}")
            print(f"   Touch detection should now be enabled on all devices")
            print("="*80 + "\n")

            return {"success": True, "course_status": self.course_status}
        except Exception as e:
            self.log(f"Activate error: {e}", level="error")
            return {"success": False, "error": "Activation failed"}

    def deactivate_course(self) -> Dict[str, Any]:
        """Stop any running course and reset devices to standby."""
        try:
            self.log("Deactivating course")
            for node_id in list(self.assignments.keys()):
                if node_id != "192.168.99.100":
                    self.send_to_node(node_id, {"cmd": "stop"})

            self.course_status = "Inactive"

            # Update server LED to amber (idle)
            if self._server_led:
                from .ft_led import LEDState
                self._server_led.set_state(LEDState.SOLID_ORANGE)
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

    # ---------------- Logs ----------------

    def clear_logs(self) -> None:
        """Clear in-memory logs (UI 'Clear' button calls this)."""
        self.logs.clear()
        self.log("System logs cleared by user")

    # ---------------- Shutdown helpers ----------------

    def shutdown_leds(self) -> None:
        """Ensure server LED (Device 0 hardware) is turned off."""
        if self._server_led:
            try:
                self._server_led.shutdown()
            except Exception:
                pass

    def set_touch_handler(self, handler_func) -> None:
        """Set the touch event handler from coach interface"""
        print(f"\n{'='*80}")
        print(f"🔗 SET_TOUCH_HANDLER CALLED")
        print(f"   Handler function: {handler_func}")
        print(f"   Handler name: {handler_func.__name__ if hasattr(handler_func, '__name__') else 'unknown'}")
        print(f"{'='*80}\n")

        self._touch_handler = handler_func
        self.log("Touch event handler registered")
    
    def handle_touch_event(self, device_id: str, timestamp: float) -> None:
        """
        Called when device reports touch event
        Forwards to coach interface for timing logic
        """
        print(f"\n{'='*80}")
        print(f"👆 HANDLE_TOUCH_EVENT CALLED")
        print(f"   Device: {device_id}")
        print(f"   Timestamp: {timestamp}")
        print(f"   Handler registered: {self._touch_handler is not None}")
        if self._touch_handler:
            print(f"   Handler function: {self._touch_handler.__name__ if hasattr(self._touch_handler, '__name__') else 'unknown'}")
        print(f"{'='*80}")

        touch_time = datetime.utcnow()
        self.log(f"Touch event: {device_id} at {touch_time.isoformat()}")
        
        if self._touch_handler:
            try:
                print(f"   📞 Calling touch handler...")
                self._touch_handler(device_id, touch_time)
                print(f"   ✅ Touch handler completed successfully")
            except Exception as e:
                print(f"   ❌ Touch handler error: {e}")
                import traceback
                traceback.print_exc()
                self.log(f"Touch handler error: {e}", level="error")
        else:
            print(f"   ⚠️  No touch handler registered - ignoring touch")
            self.log("No touch handler registered - touch event ignored", level="warning")
    
        print(f"{'='*80}\n")

    def load_active_session(self) -> None:
        """Check for active session on startup (crash recovery)"""
        if not self.db:
            return
        
        try:
            session = self.db.get_active_session()
            if session:
                if session['status'] == 'active':
                    self.log(f"Found active session {session['session_id'][:8]}... (marking incomplete due to restart)", level="warning")
                    self.db.mark_session_incomplete(
                        session['session_id'],
                        'System restart during active session'
                    )
                elif session['status'] == 'setup':
                    self.log(f"Found session in setup: {session['session_id'][:8]}...")
        except Exception as e:
            self.log(f"Error loading active session: {e}", level="error")


# Global registry instance (imported everywhere)
REGISTRY = Registry()
