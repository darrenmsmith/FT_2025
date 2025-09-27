# FT_2025
Next generation of development for Field Trainer

 Core Components:
field_trainer_core.py 
- Core device management and TCP server
- Device registry and status tracking
- TCP heartbeat server for device communication
- Course deployment and management logic
- Gateway status monitoring
 
field_trainer_web.py 
- Web interface and REST API
- Flask web application with Bootstrap UI
- REST API endpoints for course management
- Real-time device monitoring dashboard
- System logging interface

field_trainer_main.py 
- Combined application launcher
- Single entry point that starts both components
- Simplifies deployment and management

field_client_v5_2.py
- This is used for Device 0 
- provides
field_client_connections.py
- Each device has there own with the respective IP
- This is separate from Device 0 gateway

Courses.json
- Course definition (name, desc, stations, node_id


Network Configuration:
 The system expects:
- wlan0: Mesh network interface (BATMAN-adv)
- wlan1: Internet connection interface
- TCP Port 6000: Device heartbeat communication
- HTTP Port 5000: Web interface

Web Dashboard (Flask)
- Live device status with ping, battery
- Course deployment and activation controls
- Gateway mesh network status (Mesh network, SSID ft_mesh, Batman Devices, Internet, wlan1 SSID, IP, Uptime
- System event logging
- Training Circuit (Devices)

Device Communication
- TCP heartbeat protocol for reliable device connectivity
- JSON message format for course deployment
 Automatic offline detection and recovery

API Integration:
- The web component exposes REST endpoints that can be used by external systems:
- GET /api/state - Current system status
- GET /api/courses - Available courses
- POST /api/deploy - Deploy a course
- POST /api/activate - Activate deployed course
- POST /api/deactivate - Deactivate current course