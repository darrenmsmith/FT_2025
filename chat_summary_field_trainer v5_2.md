# Field Trainer v5.2 Development Chat Summary

## System Overview
- **Project**: Circuit training device management system
- **GitHub**: https://github.com/darrenmsmith/FT_2025.git  
- **Network**: Device 0 (gateway) connected to "smithhome" WiFi, shares via wlan0 mesh to Devices 1-5
- **Files**: `field_trainer_core.py`, `field_trainer_web.py`, `field_trainer_main.py`
- **Deployment**: VSCode with automated GitHub deployment to `/opt/field-trainer/app/`

## Problem Identified
**Flask interface showing 0 BATMAN neighbors despite mesh network having 5 devices**

## Root Cause Found
**Mesh cell ID mismatch** - Each device creating separate ad-hoc networks instead of joining same mesh:
- Device 0: Cell `9A:62:C3:17:18:BC`
- Device 1: Cell `7E:49:1B:61:DB:0D` 
- Device 2: Cell `56:0B:A0:5C:05:CE`
- Device 3: Cell `66:8E:58:E3:8E:38`
- Device 4: Cell `DE:42:E4:27:DE:C3`
- Device 5: Cell `F6:F2:7F:2E:F9:74`

## Technical Details
- **Network Management**: NetworkManager manages wlan1 (internet), but wlan0/bat0 are "unmanaged"
- **Mesh Service**: `mesh-ibss.service` manages wlan0 mesh via `/usr/local/bin/mesh-ibss.sh`
- **Configuration**: `/etc/default/mesh-ibss` has correct BSSID `02:12:34:56:78:9a` but devices ignore it
- **Script Issue**: IBSS networks auto-generate cells when can't find existing network with specified BSSID

## Code Fixes Applied
1. **Enhanced TCP socket handling** in `field_trainer_core.py`:
   - TCP keep-alive (30s idle, 5s interval, 3 probes)
   - Better error handling for connection drops
   - 45-second socket timeouts

2. **Fixed BATMAN neighbor detection** in `get_gateway_status()`:
   - Handles tabs in `batctl n -H` output properly
   - Function works correctly when called directly: detects 5 neighbors
   - Flask API still returns 0 due to mesh cell mismatch

## Configuration Issues Found
- **Device 2**: Wrong MESH_SSID `"mymesh"` instead of `"ft_mesh"`
- **All devices**: Same BSSID configured but creating different cells
- **Service Restart**: Device 1 mesh service fails with "Operation already in progress (-114)"
- **Driver Hang**: `iw wlan0 ibss leave` command hangs Device 1

## Current Status
- ✅ Code enhancements deployed to `/opt/field-trainer/app/`
- ✅ BATMAN neighbor detection function works correctly  
- ❌ Flask interface still shows 0 neighbors due to mesh cell mismatch
- ❌ Device 1 mesh service stuck, `iw` commands hang wireless driver
- ❌ Devices not forming unified mesh network

## Next Steps Needed
1. **Fix Device 2 SSID**: Change "mymesh" to "ft_mesh" in `/etc/default/mesh-ibss`
2. **Coordinate mesh startup**: Devices need to join same cell, not create separate ones
3. **Wireless driver recovery**: Device 1 may need reboot due to hung wireless driver
4. **Test unified mesh**: Once all devices join same cell, verify neighbor detection

## Key Commands for New Chat
```bash
# Check mesh cells
ssh pi@192.168.99.100 "iwconfig wlan0 | grep Cell"

# Test BATMAN function directly  
ssh pi@192.168.99.100 "cd /opt/field-trainer/app && python3 -c 'from field_trainer_core import get_gateway_status; print(get_gateway_status()[\"batman_neighbors\"])'"

# Check mesh service status
ssh pi@192.168.99.101 "sudo systemctl status mesh-ibss.service"

# Check API response
ssh pi@192.168.99.100 "curl -s http://localhost:5000/api/state | grep batman_neighbors"
```

## Deployment Workflow
- Edit locally in VSCode
- Use "Git: Push and Deploy" task (runs `/opt/field-trainer/scripts/github_deploy.sh`)
- Restart service: "Restart Field Trainer Service" task
- Monitor: "View Device 0 Logs" task
