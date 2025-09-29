#!/usr/bin/env python3
"""
Field Trainer – Main Application Launcher
- Starts the TCP heartbeat server
- Runs the Flask web UI
- Centralized VERSION comes from the single source of truth

CLI:
  --host 0.0.0.0   (default from env FIELD_TRAINER_HOST or 0.0.0.0)
  --port 5000      (default from env FIELD_TRAINER_PORT or 5000)
  --debug 0/1      (default from env FIELD_TRAINER_DEBUG or 0)
"""

import os
import sys
import time
import signal
import argparse
from typing import Any, Optional

# Import the web app and public API via the shim to keep imports stable
from field_trainer_core import VERSION, start_heartbeat_server, REGISTRY
from field_trainer_web import app

_SHUTDOWN_REQUESTED = False


def _signal_handler(signum, frame):
    """Flip a shutdown flag so background loops/servers can exit gracefully."""
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True


def _parse_args() -> argparse.Namespace:
    """CLI with env var fallbacks."""
    parser = argparse.ArgumentParser(description="Field Trainer - System Launcher")
    default_host = os.getenv("FIELD_TRAINER_HOST", "0.0.0.0")
    default_port = int(os.getenv("FIELD_TRAINER_PORT", "5000"))
    default_debug = bool(int(os.getenv("FIELD_TRAINER_DEBUG", "0")))
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--debug", type=lambda v: bool(int(v)), default=default_debug)
    return parser.parse_args()


def _graceful_stop(heartbeat_handle: Any) -> None:
    """
    Try common stop methods on whatever start_heartbeat_server() returned:
    - .stop() / .shutdown() / .close()
    - If it's a Thread, try .join(timeout=2)
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
    """Launch TCP heartbeat and web UI with good lifecycle & logs."""
    args = _parse_args()

    # Signals for clean stop (SIGTERM is important for containers)
    signal.signal(signal.SIGINT, _signal_handler)
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass  # Windows may not have SIGTERM

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

    # Small guard; replace with an explicit ready event if available
    time.sleep(0.25)

    REGISTRY.log("Starting web interface…")
    try:
        # Avoid the reloader foot-gun even when debug=True to prevent double-spawn
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        REGISTRY.log("Shutting down Field Trainer…")
        _graceful_stop(heartbeat_handle)
        print("System shutdown complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
