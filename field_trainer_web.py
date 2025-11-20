#!/usr/bin/env python3
"""
Field Trainer – Flask Web Interface
-----------------------------------
Responsibilities:
- Renders the dashboard (templates/index.html) with {{ version }}
- Exposes REST APIs consumed by the front-end JS
- All state is provided by REGISTRY (single source of truth)

Notes:
- This file does NOT start the heartbeat server; use field_trainer_main.py.
"""

import os
import time
from datetime import datetime
from flask import Flask, jsonify, request, render_template
from field_trainer.ft_registry import REGISTRY
from field_trainer.ft_version import VERSION

app = Flask(__name__)

# Track when this process started
START_TIME = datetime.utcnow().isoformat()

# ---------------------------- Pages ----------------------------

@app.get("/")
def index():
    """Dashboard: the template uses {{ version }} in the header and meta tags."""
    return render_template("index.html", version=VERSION)

@app.get("/health")
def health():
    """Health check endpoint - shows version and service status"""
    # If JSON requested, return JSON
    if request.args.get('format') == 'json':
        return jsonify({
            'service': 'field-trainer-admin',
            'version': VERSION,
            'pid': os.getpid(),
            'started_at': START_TIME,
            'port': 5000,
            'courses_loaded': len(REGISTRY.courses.get('courses', [])),
            'registry_id': id(REGISTRY),
            'status': 'healthy'
        })

    # Otherwise return HTML page
    health_data = {
        'service_name': 'Admin Interface',
        'version': VERSION,
        'pid': os.getpid(),
        'started_at': START_TIME,
        'port': 5000,
        'courses_loaded': len(REGISTRY.courses.get('courses', [])),
        'registry_id': id(REGISTRY),
        'course_status': REGISTRY.course_status,
        'nodes_connected': len(REGISTRY.nodes),
        'uptime': _calculate_uptime(START_TIME)
    }
    return render_template('health.html', **health_data)

def _calculate_uptime(start_time_iso):
    """Calculate uptime from ISO timestamp"""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_time_iso)
        now = datetime.utcnow()
        delta = now - start
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    except:
        return "Unknown"

# ---------------------------- Courses --------------------------

@app.route('/api/course/deploy', methods=['POST'])
def api_deploy_course():
    """API: Deploy a course"""
    data = request.get_json()
    course_name = data.get('course_name')
    if not course_name:
        return jsonify({'success': False, 'error': 'course_name required'}), 400
    result = REGISTRY.deploy_course(course_name)
    return jsonify(result)

@app.route('/api/course/activate', methods=['POST'])
def api_activate_course():
    """API: Activate deployed course"""
    data = request.get_json()
    course_name = data.get('course_name')
    if not course_name:
        return jsonify({'success': False, 'error': 'course_name required'}), 400
    result = REGISTRY.activate_course(course_name)
    return jsonify(result)

@app.get("/api/courses")
def api_courses():
    """Return the course catalog (loaded by REGISTRY at startup)."""
    return jsonify(REGISTRY.courses)

# ---------------------------- State ----------------------------

@app.get("/api/state")
def api_state():
    """
    Snapshot consumed by the UI with small enrichments:
      - per-node 'threshold' if a calibration file exists
      - 'led_status' summary (optional; computed on the fly)
    """
    import json, os

    try:
        snap = REGISTRY.snapshot()

        # ---- Enrich each node with 'threshold' if we can find its cal file ----
        cal_dir = "/opt/field-trainer/app"
        nodes = snap.get("nodes", [])
        for node in nodes:
            node_id = node.get("node_id", "")
            # Heuristic: treat the last IPv4 octet as device number (Device N)
            dev_num = None
            try:
                if node_id and node_id.count(".") == 3:
                    dev_num = int(node_id.split(".")[-1]) - 100  # e.g., 192.168.99.102 -> 2
                    if dev_num < 0 or dev_num > 99:
                        dev_num = None
            except Exception:
                dev_num = None

            if dev_num is not None:
                cal_path = os.path.join(cal_dir, f"mpu6050_cal_device{dev_num}.json")
                try:
                    if os.path.exists(cal_path):
                        with open(cal_path, "r", encoding="utf-8") as f:
                            cal = json.load(f)
                        # contributor’s code typically used 'threshold' key
                        thr = cal.get("threshold")
                        if thr is not None:
                            node["threshold"] = thr
                except Exception:
                    # Fail soft; leave threshold absent
                    pass

        # ---- LED status summary (simple, on-the-fly) ----
        # global_state: from course_status
        cs = snap.get("course_status")
        if cs == "Active":
            global_state = "course_active"
        elif cs == "Deployed":
            global_state = "course_deployed"
        else:
            global_state = "off"

        device_states = {}
        for node in nodes:
            nid = node.get("node_id")
            # Prefer node's reported led_pattern if present; otherwise infer idle/mesh
            lp = node.get("led_pattern")
            if lp:
                device_states[nid] = lp
            else:
                st = node.get("status")
                device_states[nid] = "mesh_connected" if st not in ("Offline", "Unknown") else "network_error"

        snap["led_status"] = {
            "global_state": global_state,
            "device_states": device_states,
            "device_0_led_enabled": False,   # we can wire actual flag later if needed
            "last_command_time": None        # placeholder; add if you track it
        }

        return jsonify(snap)

    except Exception as e:
        REGISTRY.log(f"State API error: {e}", level="error")
        return jsonify({"error": "Internal server error"}), 500


# ---------------------------- Logs -----------------------------

@app.get("/api/logs")
def api_logs():
    """Return recent logs (limit=n). Front-end polls this periodically."""
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    return jsonify({"events": list(REGISTRY.logs)[:limit]})

@app.post("/api/logs/clear")
def api_logs_clear():
    """Clear the in-memory system log."""
    REGISTRY.clear_logs()
    return jsonify({"success": True})

# ---------------------------- Lifecycle ------------------------

@app.post("/api/deploy")
def api_deploy():
    """
    Deploy a course by name.
    Body: {"course": "<name>"}
    """
    try:
        data = request.get_json(force=True) or {}
        course_name = data.get("course")
        if not course_name:
            return jsonify({"success": False, "error": "Course required"}), 400
        result = REGISTRY.deploy_course(course_name)
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        REGISTRY.log(f"Deploy API error: {e}", level="error")
        return jsonify({"success": False, "error": "Deployment failed"}), 500

@app.post("/api/activate")
def api_activate():
    """
    Activate the currently deployed (or provided) course.
    Body: {"course": "<name>"}  # optional
    """
    try:
        data = request.get_json(force=True) or {}
        course_name = data.get("course")
        result = REGISTRY.activate_course(course_name)
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        REGISTRY.log(f"Activate API error: {e}", level="error")
        return jsonify({"success": False, "error": "Activation failed"}), 500

@app.post("/api/deactivate")
def api_deactivate():
    """Deactivate any running course and return devices to standby."""
    try:
        result = REGISTRY.deactivate_course()
        status = 200 if result.get("success") else 400
        return jsonify(result), status
    except Exception as e:
        REGISTRY.log(f"Deactivate API error: {e}", level="error")
        return jsonify({"success": False, "error": "Deactivation failed"}), 500

@app.post("/api/audio/play")
def api_audio_play():
    """
    Play a logical clip on a device.
    Body: {"node_id": "192.168.99.100", "clip": "welcome"}
    """
    try:
        data = request.get_json(force=True) or {}
        node_id = data.get("node_id")
        clip = data.get("clip")
        if not node_id or not clip:
            return jsonify({"success": False, "error": "node_id and clip required"}), 400
        ok = REGISTRY.play_audio(node_id, clip)
        return jsonify({"success": ok})
    except Exception as e:
        REGISTRY.log(f"Audio API error: {e}", level="error")
        return jsonify({"success": False, "error": "Audio request failed"}), 500


# ---------------------- Network Info API ----------------

@app.route('/api/settings/network-info', methods=['GET'])
def get_network_info():
    """Get current network connection info (Ethernet/WiFi/AP Mode)"""
    try:
        import json
        import os
        import subprocess

        connection_type = "Unknown"
        connection_name = "Unknown"
        interface = "unknown"

        # Check for Ethernet (eth0) with IP address
        try:
            eth_result = subprocess.run(
                ['ip', 'addr', 'show', 'eth0'],
                capture_output=True, text=True, timeout=2
            )
            if eth_result.returncode == 0 and 'inet ' in eth_result.stdout:
                # eth0 has an IP address
                connection_type = "Ethernet"
                connection_name = "Ethernet (eth0)"
                interface = "eth0"
                return jsonify({
                    'success': True,
                    'ssid': connection_name,
                    'connection_type': connection_type,
                    'interface': interface
                })
        except:
            pass

        # Check network manager mode (AP mode vs online)
        network_mode = "online"
        config_file = '/opt/data/network-config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    network_mode = config.get('network_mode', {}).get('current', 'online')
            except:
                pass

        # If in AP (offline) mode
        if network_mode == 'offline':
            connection_type = "Access Point"
            connection_name = "Field_Trainer (AP Mode)"
            interface = "wlan1"
            return jsonify({
                'success': True,
                'ssid': connection_name,
                'connection_type': connection_type,
                'interface': interface
            })

        # Try to get WiFi SSID from wlan1 (primary WiFi)
        try:
            wlan1_result = subprocess.run(
                ['iwgetid', 'wlan1', '-r'],
                capture_output=True, text=True, timeout=2
            )
            if wlan1_result.returncode == 0 and wlan1_result.stdout.strip():
                ssid = wlan1_result.stdout.strip()
                connection_type = "WiFi"
                connection_name = f"{ssid} (WiFi)"
                interface = "wlan1"
                return jsonify({
                    'success': True,
                    'ssid': connection_name,
                    'connection_type': connection_type,
                    'interface': interface
                })
        except:
            pass

        # Fallback: Not connected
        return jsonify({
            'success': True,
            'ssid': 'Not connected',
            'connection_type': 'None',
            'interface': 'none'
        })

    except Exception as e:
        REGISTRY.log(f"Network info error: {e}", level="error")
        return jsonify({'success': False, 'error': str(e)}), 400


# ---------------------- Optional Device Control ----------------
# (Enable later if you add UI controls for device LEDs/audio/time.)

# @app.post("/api/device/led")
# def api_device_led():
#     data = request.get_json(force=True) or {}
#     ok = REGISTRY.set_led(data.get("node_id"), data.get("pattern"))
#     return jsonify({"success": ok})

# @app.post("/api/device/audio")
# def api_device_audio():
#     data = request.get_json(force=True) or {}
#     ok = REGISTRY.play_audio(data.get("node_id"), data.get("clip"))
#     return jsonify({"success": ok})

# @app.post("/api/device/time_sync")
# def api_device_time_sync():
#     data = request.get_json(force=True) or {}
#     ok = REGISTRY.sync_time(data.get("node_id"), data.get("controller_ms"))
#     return jsonify({"success": ok})

# ----------------------- Local dev entry -----------------------

if __name__ == "__main__":
    # For ad-hoc UI work you can run this file directly,
    # but production should use field_trainer_main.py.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
