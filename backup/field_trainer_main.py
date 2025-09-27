#!/usr/bin/env python3
"""
Field Trainer v5.2 - Main Application Launcher
- Combines core TCP server and web interface
- Single entry point for the complete system
"""

import threading
import time
from field_trainer_core import start_heartbeat_server, REGISTRY
from field_trainer_web import app

def main():
    """Launch both TCP server and web interface"""
    print("=== Field Trainer v5.2 - Circuit Training System ===")
    
    # Start TCP heartbeat server for device communication
    REGISTRY.log("Starting TCP heartbeat server...")
    tcp_server = start_heartbeat_server()
    
    # Give TCP server a moment to start
    time.sleep(0.5)
    
    # Start web interface
    REGISTRY.log("Starting web interface...")
    print("Web interface will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the system")
    
    try:
        # Run Flask app (this blocks)
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        REGISTRY.log("Shutting down Field Trainer system...")
        print("\nSystem shutdown complete.")

if __name__ == "__main__":
    main()
