// Single source of truth: injected by Jinja via <meta name="app-version">
const APP_VERSION = document.querySelector('meta[name="app-version"]')?.content || 'GetVersionFailed';


function getDeviceName(nodeId) {
    if (!nodeId) return 'Unknown Device';
    const ipParts = nodeId.split('.');
    if (ipParts.length !== 4) return nodeId;
    const deviceNum = parseInt(ipParts[3]);
    if (deviceNum === 100) return 'Start/Finish';
    if (deviceNum >= 101 && deviceNum <= 199) {
        return `Device ${deviceNum - 100}`;
    }
    return nodeId;
}

function getQualityBadge(quality) {
    if (quality >= 200) return 'bg-success';
    if (quality >= 100) return 'bg-warning';
    if (quality >= 50) return 'bg-danger';
    return 'bg-secondary';
}

function getStatusClass(status) {
    switch (status) {
        case 'Active': return 'bg-success';
        case 'Deployed': return 'bg-primary';
        case 'Inactive': default: return 'bg-secondary';
    }
}

function getDeviceStatusClass(status) {
    switch (status) {
        case 'Active': return 'bg-success';
        case 'Ready': return 'bg-primary';
        case 'Standby': return 'bg-warning';
        case 'Offline': return 'bg-danger';
        case 'Unknown': default: return 'bg-secondary';
    }
}

function updateStatus() {
    fetch('/api/state')
        .then(r => r.json())
        .then(data => {
            // Course status
            const statusEl = document.getElementById('status');
            statusEl.textContent = data.course_status || 'Inactive';
            statusEl.className = 'badge ' + getStatusClass(data.course_status);

            // Mesh status
            updateGatewayStatus(data.gateway_status);

            // Devices
            let deviceHtml = '';
            if (data.nodes && data.nodes.length > 0) {
                const sortedNodes = data.nodes.sort((a, b) => {
                    const aNum = parseInt(a.node_id.split('.').pop());
                    const bNum = parseInt(b.node_id.split('.').pop());
                    return aNum - bNum;
                });

                sortedNodes.forEach((n, index) => {
                    const deviceName = getDeviceName(n.node_id);
                    const pingText = n.ping_ms ? n.ping_ms.toFixed(1) + 'ms' : '-';
                    const batteryText = n.battery_level ? n.battery_level.toFixed(1) + '%' : '-';
                    const batteryIcon = '🔋';
                    const audioIcon = n.audio_working ? '🔈' : '🔇';
                    const accelIcon = n.accelerometer_working ? '◉' : '⌀';

                    deviceHtml += `
                    <div class="mb-2 p-2 border rounded d-flex justify-content-between align-items-center">
                        <!-- Left side: Device info -->
                        <div class="flex-grow-1">
                        <strong>${deviceName}</strong>
                        <span class="badge ${getDeviceStatusClass(n.status)}">${n.status}</span><br>
                        <small>
                            Action: ${n.action || 'None'} | Ping: ${pingText}
                        </small>
                        </div>

                        <!-- Right side: Status icons -->
                        <div class="device-icons text-end ms-3">
                            <span class="me-2" data-bs-toggle="tooltip" title="Battery Level">
                                ${batteryIcon} ${batteryText}
                            </span>
                            <span class="me-2" data-bs-toggle="tooltip" title="Audio Status">
                                ${audioIcon}
                            </span>
                            <span data-bs-toggle="tooltip" title="Accelerometer Status">
                                ${accelIcon}
                            </span>
                        </div>
                    </div>
                    `;

                });
            } else {
                deviceHtml = '<div class="text-muted">No devices connected</div>';
            }
            document.getElementById('devices').innerHTML = deviceHtml;

            // Buttons
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

    const meshStatus = gw.mesh_active
        ? `<span class="badge bg-success">Active</span>`
        : `<span class="badge bg-danger">Inactive</span>`;

    const wlan1Status = gw.wlan1_ssid !== 'Not connected'
        ? `<span class="badge bg-success">Connected</span>`
        : `<span class="badge bg-warning">Disconnected</span>`;

    const neighborsText = gw.batman_neighbors > 0
        ? `<span class="badge bg-success">${gw.batman_neighbors} devices</span>`
        : `<span class="badge bg-warning">No neighbors</span>`;

    // Status group (badges)
    let statusHtml = `
      <div class="row g-2 mb-2">
        <div class="col-6"><strong>Mesh Network:</strong></div>
        <div class="col-6">${meshStatus}</div>

        <div class="col-6"><strong>Internet (WLAN1):</strong></div>
        <div class="col-6">${wlan1Status}</div>

        <div class="col-6"><strong>B.A.T.M.A.N. Devices:</strong></div>
        <div class="col-6">${neighborsText}</div>
      </div>
      <hr class="my-2">
    `;

    // Details group (plain text)
    let detailsHtml = `
      <div class="row g-2 mb-2">
        <div class="col-6"><strong>SSID:</strong></div>
        <div class="col-6"><span class="value">${gw.mesh_ssid}</span></div>

        <div class="col-6"><strong>Gateway Cell:</strong></div>
        <div class="col-6"><span class="value">${gw.mesh_cell ? gw.mesh_cell.substring(0, 8) : 'Unknown'}</span></div>

        <div class="col-6"><strong>WLAN1 SSID:</strong></div>
        <div class="col-6"><span class="value">${gw.wlan1_ssid}</span></div>

        <div class="col-6"><strong>WLAN1 IP:</strong></div>
        <div class="col-6"><span class="value">${gw.wlan1_ip}</span></div>

        <div class="col-6"><strong>Uptime:</strong></div>
        <div class="col-6"><span class="value">${gw.uptime}</span></div>
      </div>
    `;

    // Mesh devices (grouped badges + values)
    let meshDevicesHtml = '';
    if (gw.mesh_devices && gw.mesh_devices.length > 0) {
        meshDevicesHtml = '<hr class="my-2"><div class="mt-1"><strong>Mesh Devices:</strong>';
        gw.mesh_devices.forEach(device => {
            const qualityBadge = getQualityBadge(device.connection_quality);
            const statusBadge = device.status === 'Active' ? 'bg-success' : 'bg-warning';
            const lastSeenSec = (device.last_seen_ms / 1000).toFixed(1);


            meshDevicesHtml += `
              <div class="row g-2 align-items-center mb-1">
                <div class="col-6">
                  <span class="value">${device.device_name}</span>
                  <span class="badge ${statusBadge} ms-1">${device.status}</span>
                </div>
                <div class="col-6">
                  <span class="badge ${qualityBadge}">Q:${device.connection_quality}</span>
                  <span class="value ms-2">Last: ${lastSeenSec}s</span>
                </div>
              </div>`;
        });
        meshDevicesHtml += '</div>';
    }

    // Mesh statistics
    let statsHtml = '';
    if (gw.mesh_statistics && Object.keys(gw.mesh_statistics).length > 0) {
        statsHtml = '<hr class="my-2"><div class="mt-1"><strong>Mesh Stats:</strong>';
        Object.entries(gw.mesh_statistics).slice(0, 3).forEach(([key, value]) => {
            statsHtml += `
              <div class="row">
                <div class="col-6"><strong>${key}:</strong></div>
                <div class="col-6"><span class="value">${value}</span></div>
              </div>`;
        });
        statsHtml += '</div>';
    }

    // Render everything
    document.getElementById('gatewayStatus').innerHTML =
        statusHtml + detailsHtml + meshDevicesHtml + statsHtml;
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
                }).join('\n');
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course: course })
    }).then(r => r.json())
        .then(() => { updateStatus(); refreshLogs(); })
        .catch(e => console.error('Deploy error:', e));
}

function activateClick() {
    const course = document.getElementById('courseSelect').value;
    if (!course) return;
    fetch('/api/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course: course })
    }).then(r => r.json())
        .then(() => { updateStatus(); refreshLogs(); })
        .catch(e => console.error('Activate error:', e));
}

function deactivateClick() {
    fetch('/api/deactivate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}'
    }).then(r => r.json())
        .then(() => { updateStatus(); refreshLogs(); })
        .catch(e => console.error('Deactivate error:', e));
}

function clearLogs() {
    fetch('/api/logs/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}'
    }).then(() => refreshLogs())
        .catch(e => console.error('Clear logs error:', e));
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('courseSelect').addEventListener('change', updateStatus);
    loadCourses();
    updateStatus();
    refreshLogs();
    setInterval(updateStatus, 3000);
    setInterval(refreshLogs, 5000);
});
