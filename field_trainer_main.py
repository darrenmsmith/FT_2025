#!/usr/bin/env python3
"""
Field Trainer – Main Application Launcher
-------------------------------------------------
Starts:
  1) The TCP heartbeat server (devices connect here)
  2) The Flask web UI (dashboard + REST API)

Key characteristics:
- Single version source imported from field_trainer.ft_version
- Clean signal handling (Ctrl+C and SIGTERM)
- Graceful shutdown: stop heartbeat + turn off server LEDs (if enabled)
- CLI flags with environment fallbacks

CLI:
  python field_trainer_main.py --host 0.0.0.0 --port 5000 --debug 0
ENV:
  FIELD_TRAINER_HOST, FIELD_TRAINER_PORT, FIELD_TRAINER_DEBUG
"""

import os
import sys
import time
import signal
import argparse
import threading
from typing import Any, Optional

# Public API imports (web app + system services)
from field_trainer.ft_version import VERSION
from field_trainer.ft_heartbeat import start_heartbeat_server
from field_trainer.ft_registry import REGISTRY
from field_trainer_web import app  # Flask app instance & routes

# Global shutdown flag (if you add background loops later, they can poll this)
_SHUTDOWN_REQUESTED = False


def _signal_handler(signum, frame):
    """Basic signal handler: flip a flag so long-running tasks can exit promptly."""
    del signum, frame
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True


def _parse_args() -> argparse.Namespace:
    """Parse CLI args with environment-based defaults."""
    parser = argparse.ArgumentParser(description="Field Trainer - System Launcher")
    default_host = os.getenv("FIELD_TRAINER_HOST", "0.0.0.0")
    default_port = int(os.getenv("FIELD_TRAINER_PORT", "5000"))
    default_debug = bool(int(os.getenv("FIELD_TRAINER_DEBUG", "0")))
    parser.add_argument("--host", default=default_host, help="Web host (default env FIELD_TRAINER_HOST)")
    parser.add_argument("--port", type=int, default=default_port, help="Web port (default env FIELD_TRAINER_PORT)")
    parser.add_argument("--debug", type=lambda v: bool(int(v)), default=default_debug, help="Flask debug (0/1)")
    return parser.parse_args()


def _graceful_stop(heartbeat_handle: Any) -> None:
    """
    Try to gracefully stop whatever start_heartbeat_server() returned.
    Defensive approach: try common shutdown methods; if it's a Thread, try join.
    """
    if heartbeat_handle is None:
        return
    for name in ("stop", "shutdown", "close"):
        fn = getattr(heartbeat_handle, name, None)
        if callable(fn):
            try:
                fn()
            except Exception as e:
                REGISTRY.log(f"Heartbeat {name}() failed: {e}", level="error")
    try:
        import threading
        if isinstance(heartbeat_handle, threading.Thread):
            heartbeat_handle.join(timeout=2.0)
    except Exception:
        pass


def main() -> int:
    """Boot both services and handle lifecycle cleanly."""
    args = _parse_args()

    # Signals: SIGINT (Ctrl+C) and SIGTERM (containers)
    signal.signal(signal.SIGINT, _signal_handler)
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        # Windows may not support SIGTERM; ignore if unsupported.
        pass

    print(f"=== Field Trainer {VERSION} – Circuit Training System ===")
    print(f"Web: http://{args.host}:{args.port}  (debug={int(args.debug)})")
    print("Press Ctrl+C to stop")

    # Start heartbeat server
    REGISTRY.log("Starting TCP heartbeat server…")
    try:
        heartbeat_handle: Optional[Any] = start_heartbeat_server()
    except Exception as e:
        REGISTRY.log(f"Failed to start heartbeat server: {e}", level="error")
        print("ERROR: Heartbeat server failed. See logs.")
        return 1

    # Database initialization and course migration (Phase 1)
    REGISTRY.load_active_session()
    
    # Migrate courses if database is empty
    if REGISTRY.db and len(REGISTRY.db.get_all_courses()) == 0:
        REGISTRY.log("Migrating courses to database...")
        from field_trainer.ft_courses import load_courses
        courses_data = load_courses()
        REGISTRY.db.migrate_courses_from_json(courses_data)
        REGISTRY.log("Course migration complete")
    
    # Start coach interface (Phase 1)
    
    try:
        import coach_interface as coach_app
        
        #         # Call the registration function from coach_interface
        #         coach_app.register_touch_handler()
        #         
        #         def run_coach_interface():
        #             coach_app.app.run(host='0.0.0.0', port=5001, use_reloader=False, debug=False)
        #         coach_thread = threading.Thread(target=run_coach_interface, daemon=True)
        #         coach_thread.start()
        #         REGISTRY.log("Coach interface started on port 5001")
    except Exception as e:
        REGISTRY.log(f"Failed to start coach interface: {e}", level="error")

    # Small guard; swap for an explicit "ready" event if you add one later.
    time.sleep(0.25)

    REGISTRY.log("Starting web interface…")
    try:
        # Important: use_reloader=False prevents duplicate processes when debug is enabled
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        # Always shut down LEDs first (so hardware turns off), then the server.
        REGISTRY.log("Shutting down Field Trainer…")
        try:
            REGISTRY.shutdown_leds()
        except Exception:
            pass
        _graceful_stop(heartbeat_handle)
        print("System shutdown complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
