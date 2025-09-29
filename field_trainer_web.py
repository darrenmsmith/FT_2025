#!/usr/bin/env python3
"""
Field Trainer – Flask Web Interface
- Renders the dashboard (templates/index.html)
- Exposes REST APIs used by the UI
- Imports VERSION from the single source of truth
"""

from flask import Flask, jsonify, request, render_template
# Public API shim keeps existing imports stable
from field_trainer_core import REGISTRY, VERSION

# --------------------------------------------------------------------
# Flask app
# --------------------------------------------------------------------
app = Flask(__name__)

@app.get("/")
def index():
    """
    Main dashboard.
    The template uses {{ version }} in the header, fed from VERSION.
    """
    return render_template("index.html", version=VERSION)

# ----------------------- REST: Courses -------------------------------

@app.get("/api/courses")
def api_courses():
    """
    Return the course catalog as provided by the registry.
    Shape: {"courses": [ ... ]}
    """
    return jsonify(REGISTRY.courses)

# ----------------------- REST: System State --------------------------

@app.get("/api/state")
def api_state():
    """
    Snapshot consumed by the UI:
      - course_status, selected_course
      - nodes[]
      - gateway_status (mesh/wifi details)
      - version
    """
    try:
        return jsonify(REGISTRY.snapshot())
    except Exception as e:
        REGISTRY.log(f"State API error: {e}", level="error")
        return jsonify({"error": "Internal server error"}), 500

# ----------------------- REST: Logs ---------------------------------

@app.get("/api/logs")
def api_logs():
    """
    Return recent logs (default limit=100).
    UI polls this periodically.
    """
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

# ----------------------- REST: Course Lifecycle ----------------------

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

# --------------------------------------------------------------------
# Local dev entry (optional). In production, prefer field_trainer_main.py
# --------------------------------------------------------------------
if __name__ == "__main__":
    # For ad-hoc dev you can run: python field_trainer_web.py
    # Keep reloader off to avoid double-spawn; adjust debug as desired.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
