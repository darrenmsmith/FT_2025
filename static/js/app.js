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
        case 'Active': return 'bg-success';      // Green
        case 'Deployed': return 'bg-primary';    // Blue
        case 'Standby': return 'bg-warning';     // Orange
        case 'Offline': return 'bg-danger';      // Red
        case 'Unknown': default: return 'bg-secondary';
    }
}

function formatLastSeen(isoStr) {
    if (!isoStr) return 'never';
    try {
        const date = new Date(isoStr);
        const diff = Math.floor((Date.now() - date) / 1000);
        if (diff < 5) return 'just now';
        if (diff < 60) return diff + 's ago';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        return Math.floor(diff / 3600) + 'h ago';
    } catch (e) {
        return '?';
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
                    const audioIcon = n.audio_working ? '🔈' : '🔇';
                    const lastSeen = formatLastSeen(n.last_msg);
                    const isVirtual = n.node_id === '192.168.99.100';
                    const rebootBtn = !isVirtual
                        ? `<button class="btn btn-sm btn-danger ms-1" onclick="rebootDevice('${n.node_id}', '${deviceName}')" title="Reboot device">&#x21BA; Reboot</button>`
                        : '';

                    deviceHtml += `
                    <div class="mb-2 p-2 border rounded d-flex justify-content-between align-items-center">
                        <div class="flex-grow-1">
                            <strong>${deviceName}</strong>
                            <span class="badge ${getDeviceStatusClass(n.status)}">${n.status}</span><br>
                            <small>
                                Action: ${n.action || 'None'} | Ping: ${pingText} | Seen: ${lastSeen}
                            </small>
                        </div>
                        <div class="device-icons text-end ms-2">
                            <span title="Audio Status">${audioIcon}</span>
                            ${rebootBtn}
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

    const neighborsCount = gw.batman_neighbors || 0;
    const neighborsLabel = neighborsCount === 1 ? 'device' : 'devices';
    const neighborsBadgeClass = neighborsCount > 0 ? 'bg-success' : 'bg-secondary';
    const neighborsNote = gw.batman_neighbors_fallback ? ' (via registry)' : '';
    const neighborsText = `<span class="badge ${neighborsBadgeClass}">${neighborsCount} ${neighborsLabel}${neighborsNote}</span>`;

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
        statusHtml + detailsHtml + statsHtml;
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

function downloadLogs() {
    const logEl = document.getElementById('logs');
    const text = logEl ? logEl.textContent : 'No logs';
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'field-trainer-log-' + new Date().toISOString().slice(0, 19).replace(/:/g, '-') + '.txt';
    a.click();
    URL.revokeObjectURL(url);
}

function rebootDevice(nodeId, deviceName) {
    if (!confirm('Reboot ' + deviceName + '?\nThe device will disconnect briefly and rejoin the mesh.')) return;
    fetch('/api/device/reboot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId })
    }).then(r => r.json())
      .then(data => {
          if (data.success) {
              refreshLogs();
          } else {
              alert('Reboot failed: ' + (data.error || 'Unknown error'));
          }
      })
      .catch(e => { console.error('Reboot error:', e); alert('Reboot request failed'); });
}

function restartService() {
    if (!confirm('Restart the Field Trainer service on the gateway?\nThis will briefly interrupt all connected devices.')) return;
    fetch('/api/restart-service', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}'
    }).then(r => r.json())
      .then(data => {
          if (data.success) {
              document.getElementById('logs').textContent = 'Service restarting... page will reload in 8 seconds.';
              setTimeout(() => location.reload(), 8000);
          } else {
              alert('Restart failed: ' + (data.error || 'Unknown error'));
          }
      })
      .catch(() => {
          // Expected: connection drops during restart
          document.getElementById('logs').textContent = 'Service restarting... page will reload in 8 seconds.';
          setTimeout(() => location.reload(), 8000);
      });
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('courseSelect').addEventListener('change', updateStatus);
    loadCourses();
    updateStatus();
    refreshLogs();
    setInterval(updateStatus, 3000);
    setInterval(refreshLogs, 5000);
});
