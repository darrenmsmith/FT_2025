#!/usr/bin/env python3
"""
Field Trainer Web Interface v5.2 - Flask Web Application
- Web dashboard for circuit training management
- REST API for course deployment and monitoring
- Real-time device status and logging
"""

from flask import Flask, jsonify, request
from field_trainer_core import REGISTRY, start_heartbeat_server

# Configuration
HOST = "0.0.0.0"
HTTP_PORT = 5000

# Flask Web App
app = Flask(__name__)

@app.get("/")
def index():
    return '''<!DOCTYPE html>
<html>
<head>
<title>Field Trainer v5.2</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="p-4">
<h1>Field Trainer v5.2 - Circuit Training</h1>

<div class="row">
  <div class="col-md-4">
    <div class="card">
      <div class="card-header">Course Management</div>
      <div class="card-body">
        <div class="mb-3">
          Status: <span id="status" class="badge bg-secondary">Loading...</span>
        </div>
        <select id="courseSelect" class="form-select mb-3">
          <option>Loading courses...</option>
        </select>
        <button id="deployBtn" class="btn btn-primary me-2" onclick="deployClick()">Deploy</button>
        <button id="activateBtn" class="btn btn-success" onclick="activateClick()">Activate</button>
        <button id="deactivateBtn" class="btn btn-outline-secondary ms-2" onclick="deactivateClick()">Deactivate</button>
      </div>
    </div>
  </div>
  
  <div class="col-md-4">
    <div class="card">
      <div class="card-header">Gateway Status</div>
      <div class="card-body">
        <div id="gatewayStatus">Loading gateway status...</div>
      </div>
    </div>
  </div>
  
  <div class="col-md-4">
    <div class="card">
      <div class="card-header">Training Circuit</div>
      <div class="card-body">
        <div id="devices">No devices connected</div>
      </div>
    </div>
  </div>
</div>

<div class="card mt-3">
  <div class="card-header d-flex justify-content-between">
    <span>System Log</span>
    <button class="btn btn-sm btn-outline-secondary" onclick="clearLogs()">Clear</button>
  </div>
  <div class="card-body">
    <pre id="logs" style="height:250px; overflow-y:auto; background:#f8f9fa; font-size:0.85em;">Loading logs...</pre>
  </div>
</div>

<script>
function updateStatus() {
  fetch('/api/state')
    .then(r => r.json())
    .then(data => {
      // Update course status
      const statusEl = document.getElementById('status');
      statusEl.textContent = data.course_status || 'Inactive';
      statusEl.className = 'badge ' + getStatusClass(data.course_status);
      
      // Update gateway status
      updateGatewayStatus(data.gateway_status);
      
      // Update devices display - show as circuit order
      let deviceHtml = '';
      if (data.nodes && data.nodes.length > 0) {
        // Sort devices by node_id to show circuit order (0, 1, 2, 3, 4, 5)
        const sortedNodes = data.nodes.sort((a, b) => {
          const aNum = parseInt(a.node_id.split('.').pop());
          const bNum = parseInt(b.node_id.split('.').pop());
          return aNum - bNum;
        });
        
        sortedNodes.forEach((n, index) => {
          const nodeNum = n.node_id.split('.').pop() || n.node_id;
          const deviceName = nodeNum === '100' ? 'Start/Finish' : `Device ${nodeNum}`;
          const pingText = n.ping_ms ? n.ping_ms + 'ms' : '-';
          const batteryText = n.battery_level ? n.battery_level + '%' : '-';
          const audioIcon = n.audio_working ? '🔊' : '🔇';
          const accelIcon = n.accelerometer_working ? '📱' : '❌';
          const arrow = index < sortedNodes.length - 1 ? ' ➔ ' : '';
          
          deviceHtml += `
            <div class="mb-2 p-2 border rounded d-flex align-items-center">
              <div class="flex-grow-1">
                <strong>${deviceName}</strong> 
                <span class="badge ${getDeviceStatusClass(n.status)}">${n.status}</span><br>
                <small>Action: ${n.action || 'None'} | Ping: ${pingText} | Battery: ${batteryText} ${audioIcon}${accelIcon}</small>
              </div>
              ${arrow ? '<div class="text-primary fs-4">' + arrow + '</div>' : ''}
            </div>
          `;
        });
      } else {
        deviceHtml = '<div class="text-muted">No devices connected</div>';
      }
      document.getElementById('devices').innerHTML = deviceHtml;
      
      // Update button states
      const hasDevices = data.nodes && data.nodes.length > 0;
      const courseSelected = document.getElementById('courseSelect').value;
      
      document.getElementById('deployBtn').disabled = !courseSelected || !hasDevices;
      document.getElementById('activateBtn').disabled = data.course_status !== 'Deployed';
      document.getElementById('deactivateBtn').disabled = data.course_status === 'Inactive';
    })
    .catch(e => console.error('State error:', e));
}

function updateGatewayStatus(gw) {
  if (!gw) return;
  
  const meshStatus = gw.mesh_active ? 
    `<span class="badge bg-success">Active</span>` : 
    `<span class="badge bg-danger">Inactive</span>`;
  
  const neighborsText = gw.batman_neighbors > 0 ? 
    `<span class="badge bg-success">${gw.batman_neighbors} devices</span>` :
    `<span class="badge bg-warning">No neighbors</span>`;
  
  const wlan1Status = gw.wlan1_ssid !== 'Not connected' ?
    `<span class="badge bg-success">Connected</span>` :
    `<span class="badge bg-warning">Disconnected</span>`;

  const gatewayHtml = `
    <div class="row g-2">
      <div class="col-6"><strong>Mesh Network:</strong></div>
      <div class="col-6">${meshStatus}</div>
      
      <div class="col-6"><strong>SSID:</strong></div>
      <div class="col-6"><code>${gw.mesh_ssid}</code></div>
      
      <div class="col-6"><strong>BATMAN Devices:</strong></div>
      <div class="col-6">${neighborsText}</div>
      
      <div class="col-6"><strong>Internet (wlan1):</strong></div>
      <div class="col-6">${wlan1Status}</div>
      
      <div class="col-6"><strong>wlan1 SSID:</strong></div>
      <div class="col-6"><code>${gw.wlan1_ssid}</code></div>
      
      <div class="col-6"><strong>wlan1 IP:</strong></div>
      <div class="col-6"><code>${gw.wlan1_ip}</code></div>
      
      <div class="col-6"><strong>Uptime:</strong></div>
      <div class="col-6">${gw.uptime}</div>
    </div>
  `;
  
  document.getElementById('gatewayStatus').innerHTML = gatewayHtml;
}

function getStatusClass(status) {
  switch(status) {
    case 'Active': return 'bg-success';
    case 'Deployed': return 'bg-primary';
    case 'Inactive': default: return 'bg-secondary';
  }
}

function getDeviceStatusClass(status) {
  switch(status) {
    case 'Active': return 'bg-success';
    case 'Ready': return 'bg-primary';
    case 'Standby': return 'bg-warning';
    case 'Offline': return 'bg-danger';
    case 'Unknown': default: return 'bg-secondary';
  }
}

function refreshLogs() {
  fetch('/api/logs')
    .then(r => r.json())
    .then(data => {
      if (data.events && data.events.length > 0) {
        const logText = data.events.map(e => {
          const time = e.ts.split('T')[1].split('+')[0];
          const nodeId = e.node_id ? '(' + e.node_id.split('.').pop() + ')' : '';
          return `[${time}] ${e.level.toUpperCase()} ${nodeId}: ${e.msg}`;
        }).join('\\n');
        document.getElementById('logs').textContent = logText;
      } else {
        document.getElementById('logs').textContent = 'No log entries...';
      }
    })
    .catch(e => console.error('Logs error:', e));
}

function loadCourses() {
  fetch('/api/courses')
    .then(r => r.json())
    .then(data => {
      const select = document.getElementById('courseSelect');
      select.innerHTML = '<option value="">Select course...</option>';
      if (data.courses) {
        data.courses.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.name;
          opt.textContent = `${c.name} - ${c.description}`;
          select.appendChild(opt);
        });
      }
    })
    .catch(e => console.error('Courses error:', e));
}

function deployClick() {
  const course = document.getElementById('courseSelect').value;
  if (!course) return;
  
  fetch('/api/deploy', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({course: course})
  })
  .then(r => r.json())
  .then(data => {
    console.log('Deploy result:', data);
    updateStatus();
    refreshLogs();
  })
  .catch(e => console.error('Deploy error:', e));
}

function activateClick() {
  const course = document.getElementById('courseSelect').value;
  if (!course) return;
  
  fetch('/api/activate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({course: course})
  })
  .then(r => r.json())
  .then(data => {
    console.log('Activate result:', data);
    updateStatus();
    refreshLogs();
  })
  .catch(e => console.error('Activate error:', e));
}

function deactivateClick() {
  fetch('/api/deactivate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({})
  })
  .then(r => r.json())
  .then(data => {
    console.log('Deactivate result:', data);
    updateStatus();
    refreshLogs();
  })
  .catch(e => console.error('Deactivate error:', e));
}

function clearLogs() {
  fetch('/api/logs/clear', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}'
  })
  .then(() => refreshLogs())
  .catch(e => console.error('Clear logs error:', e));
}

// Event handlers
document.getElementById('courseSelect').addEventListener('change', updateStatus);

// Initialize
loadCourses();
updateStatus();
refreshLogs();

// Auto-refresh
setInterval(updateStatus, 3000);
setInterval(refreshLogs, 5000);
</script>
</body>
</html>'''

@app.get("/api/courses")
def api_courses():
    return jsonify(REGISTRY.courses)

@app.get("/api/state")
def api_state():
    try:
        return jsonify(REGISTRY.snapshot())
    except Exception as e:
        REGISTRY.log(f"State API error: {e}", level="error")
        return jsonify({"error": "Internal server error"}), 500

@app.get("/api/logs")
def api_logs():
    limit = int(request.args.get("limit", 100))
    return jsonify({"events": list(REGISTRY.logs)[:limit]})

@app.post("/api/logs/clear")
def api_logs_clear():
    REGISTRY.clear_logs()
    return jsonify({"success": True})

@app.post("/api/deploy")
def api_deploy():
    try:
        data = request.get_json(force=True)
        course_name = data.get("course")
        if not course_name:
            return jsonify({"success": False, "error": "Course required"}), 400
            
        result = REGISTRY.deploy_course(course_name)
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        REGISTRY.log(f"Deploy API error: {e}", level="error")
        return jsonify({"success": False, "error": "Deployment failed"}), 500

@app.post("/api/activate")
def api_activate():
    try:
        data = request.get_json(force=True)
        course_name = data.get("course")
        
        result = REGISTRY.activate_course(course_name)
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        REGISTRY.log(f"Activate API error: {e}", level="error")
        return jsonify({"success": False, "error": "Activation failed"}), 500

@app.post("/api/deactivate")
def api_deactivate():
    try:
        result = REGISTRY.deactivate_course()
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        REGISTRY.log(f"Deactivate API error: {e}", level="error")
        return jsonify({"success": False, "error": "Deactivation failed"}), 500

if __name__ == "__main__":
    # Start the TCP heartbeat server
    start_heartbeat_server()
    REGISTRY.log("Field Trainer Web Interface v5.2 starting")
    
    # Start the Flask web server
    app.run(host=HOST, port=HTTP_PORT, debug=False)
