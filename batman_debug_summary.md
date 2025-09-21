# BATMAN Neighbor Detection Debug Summary

## Problem Statement
Field Trainer Flask web interface shows `batman_neighbors: 0` despite BATMAN mesh network having active neighbors.

## System Status
- **GitHub Repo**: https://github.com/darrenmsmith/FT_2025.git
- **Deployment Path**: `/opt/field-trainer/app/`
- **Network**: 4-device mesh (Devices 0, 1, 4, 5) - Devices 2, 3 offline after hard reset
- **Current State**: Only Device 1 (101) connected and pingable

## Root Cause Identified
**Flask HTTP responses return stale data while Flask application itself works correctly**

## Debugging Results

### ✅ Working Components
```bash
# Direct function call - WORKS
cd /opt/field-trainer/app && python3 -c "from field_trainer_core import get_gateway_status; print(get_gateway_status()['batman_neighbors'])"
# Returns: 1 (with debug output showing correct parsing)

# REGISTRY.snapshot() - WORKS  
python3 -c "from field_trainer_core import REGISTRY; print(REGISTRY.snapshot()['gateway_status']['batman_neighbors'])"
# Returns: 1

# Flask test client - WORKS
python3 -c "from field_trainer_web import app; client = app.test_client(); print(client.get('/api/state').get_json()['gateway_status']['batman_neighbors'])"
# Returns: 1
```

### ❌ Broken Component
```bash
# HTTP endpoint - BROKEN
curl -s http://localhost:5000/api/state | grep batman_neighbors
# Returns: "batman_neighbors":0
```

## Enhanced Code Status
- **Function deployed**: ✅ Enhanced `get_gateway_status()` with tab parsing in `/opt/field-trainer/app/field_trainer_core.py`
- **Function works**: ✅ Correctly detects 1 BATMAN neighbor with debug output
- **Import path fixed**: ✅ Removed conflicting `/home/pi/field_trainer_core.py` 
- **Service configured**: ✅ systemd service uses correct working directory

## The Mystery
**Flask application returns correct data (1 neighbor) but HTTP requests return wrong data (0 neighbors)**

This indicates:
- Flask endpoint correctly calls `REGISTRY.snapshot()`
- Enhanced function executes properly (debug output visible)
- JSON serialization works
- **HTTP response layer is corrupted/cached**

## Technical Evidence
```bash
# BATMAN mesh working
sudo batctl n  # Shows 1 neighbor: b8:27:eb:60:3c:54
ping 192.168.99.101  # Success

# Enhanced function working
# Debug output: "BATMAN: Found 1 mesh neighbors total"
# Function result: 1

# Flask test vs HTTP discrepancy
# Flask test client: batman_neighbors: 1  
# HTTP curl: batman_neighbors: 0
```

## Regression Analysis
User noted: "this used to work in a previous version of the code"

Suggests our TCP socket enhancements introduced a side effect affecting Flask's HTTP response generation while keeping the underlying function working.

## Potential Causes
1. **Threading conflict** - Enhanced TCP handler interfering with Flask HTTP responses
2. **Import timing issue** - Module loading affecting Flask response generation  
3. **Flask middleware problem** - HTTP layer returning cached/stale responses
4. **Race condition** - Timing difference between test client (sync) and HTTP (async)

## Current Workaround
None. System functionally works (mesh network active, devices communicating) but web interface shows incorrect neighbor count.

## Next Steps for Resolution
1. **Compare with working version** - Identify specific changes that caused regression
2. **Test without TCP enhancements** - Temporarily disable enhanced TCP code to isolate issue
3. **Flask debugging** - Add HTTP response logging to trace where wrong data originates
4. **Service restart investigation** - Determine why multiple service restarts don't fix HTTP responses

## Files Modified
- `/opt/field-trainer/app/field_trainer_core.py` - Enhanced `get_gateway_status()` function
- Enhanced TCP socket handling (HeartbeatHandler, ThreadedTCPServer)

## Configuration Details
```bash
# Service: /etc/systemd/system/field-trainer.service
# WorkingDirectory: /opt/field-trainer/app
# PYTHONPATH: /opt/field-trainer/app
# Process: Single instance running correctly
```
