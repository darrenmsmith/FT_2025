/**
 * Settings Page JavaScript
 * Handles loading and auto-saving system settings
 */

// State
let originalSettings = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    attachEventListeners();
    loadTestAudioPreferences();
});

/**
 * Load all settings from API
 */
async function loadSettings() {
    console.log('[Settings] Starting to load settings...');
    try {
        const response = await fetch('/api/settings');
        console.log('[Settings] API response status:', response.status);

        const data = await response.json();
        console.log('[Settings] API data:', data);

        if (!data.success) {
            console.error('[Settings] API returned error:', data.error);
            showStatus('Error loading settings: ' + data.error, 'danger');
            return;
        }

        originalSettings = { ...data.settings };

        console.log('[Settings] Calling populateSettings...');
        populateSettings(data.settings);

        console.log('[Settings] Calling populateAudioFiles...');
        populateAudioFiles(data.audio_files, data.root_audio_files);

        // Set ready_audio_file value AFTER dropdown is populated
        const audioFile = data.settings.ready_audio_file || '';
        if (audioFile) {
            const readyAudioSelect = document.getElementById('ready_audio_file');
            if (readyAudioSelect) {
                readyAudioSelect.value = audioFile;
                console.log(`[Settings] Set ready_audio_file to: ${audioFile}`);
            }
        }

        console.log('[Settings] Calling loadCurrentNetwork...');
        loadCurrentNetwork();

        console.log('[Settings] ✓ Settings loaded successfully');
        showStatus('Settings loaded successfully', 'success');
    } catch (error) {
        console.error('[Settings] Exception loading settings:', error);
        showStatus('Failed to load settings: ' + error.message, 'danger');
    }
}

/**
 * Populate form fields with settings values
 */
function populateSettings(settings) {
    // Distance unit radio buttons
    const distanceUnit = settings.distance_unit || 'yards';
    document.querySelector(`input[name="distance_unit"][value="${distanceUnit}"]`).checked = true;

    // Voice gender radio buttons
    const voiceGender = settings.voice_gender || 'male';
    document.querySelector(`input[name="voice_gender"][value="${voiceGender}"]`).checked = true;

    // System volume slider
    const volume = settings.system_volume || '60';
    document.getElementById('system_volume').value = volume;
    document.getElementById('volume-display').textContent = volume;

    // Ready audio file dropdown - NOTE: value is set AFTER populateAudioFiles() in loadSettings()

    // Timing defaults
    document.getElementById('min_travel_time').value = settings.min_travel_time || '1';
    document.getElementById('max_travel_time').value = settings.max_travel_time || '15';

    // Device behavior
    document.getElementById('ready_led_color').value = settings.ready_led_color || 'orange';
    // ready_audio_target was removed from UI

    // Network configuration
    document.getElementById('wifi_ssid').value = settings.wifi_ssid || '';
    document.getElementById('wifi_password').value = settings.wifi_password || '';
}

/**
 * Populate audio files dropdown
 */
function populateAudioFiles(allFiles, rootFiles) {
    console.log('[Settings] Populating audio files - all:', allFiles ? allFiles.length : 0, 'root:', rootFiles ? rootFiles.length : 0);

    // Populate dropdowns with different file lists
    const selects = [
        { id: 'ready_audio_file', elem: document.getElementById('ready_audio_file'), files: rootFiles },  // Only root files for ready notification
        { id: 'test_audio_file', elem: document.getElementById('test_audio_file'), files: allFiles }       // All files for testing
    ];

    selects.forEach(({ id, elem: select, files }) => {
        if (!select) {
            console.error(`[Settings] Element not found: ${id}`);
            return;
        }

        // Keep the first option (-- Select Audio File --)
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add audio files
        if (files && files.length > 0) {
            files.forEach(file => {
                const option = document.createElement('option');
                option.value = file;
                option.textContent = file;
                select.appendChild(option);
            });
            console.log(`[Settings] Populated ${id} with ${files.length} files`);
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No audio files found';
            option.disabled = true;
            select.appendChild(option);
            console.warn(`[Settings] No audio files found for ${id}`);
        }
    });
}

/**
 * Load test audio preferences from localStorage
 */
function loadTestAudioPreferences() {
    try {
        // Load test device selection
        const savedDevice = localStorage.getItem('test_device');
        if (savedDevice) {
            const deviceSelect = document.getElementById('test_device');
            if (deviceSelect) {
                deviceSelect.value = savedDevice;
            }
        }

        // Load test audio file selection
        const savedAudioFile = localStorage.getItem('test_audio_file');
        if (savedAudioFile) {
            const audioSelect = document.getElementById('test_audio_file');
            if (audioSelect) {
                // Wait a bit for audio files to load
                setTimeout(() => {
                    audioSelect.value = savedAudioFile;
                }, 500);
            }
        }

        console.log('[Settings] Loaded test audio preferences from localStorage');
    } catch (error) {
        console.error('[Settings] Error loading test audio preferences:', error);
    }
}

/**
 * Save test audio preferences to localStorage
 */
function saveTestAudioPreferences() {
    try {
        const device = document.getElementById('test_device').value;
        const audioFile = document.getElementById('test_audio_file').value;

        localStorage.setItem('test_device', device);
        localStorage.setItem('test_audio_file', audioFile);

        console.log('[Settings] Saved test audio preferences to localStorage');
    } catch (error) {
        console.error('[Settings] Error saving test audio preferences:', error);
    }
}

/**
 * Attach event listeners to all form inputs
 */
function attachEventListeners() {
    // Reset button
    document.getElementById('reset-btn').addEventListener('click', confirmReset);

    // Password toggle
    document.getElementById('toggle-password').addEventListener('click', togglePasswordVisibility);

    // Play audio button
    document.getElementById('play-audio-btn').addEventListener('click', playSelectedAudio);

    // LED test button
    document.getElementById('test-led-btn').addEventListener('click', testLED);

    // Volume slider - update display on input
    document.getElementById('system_volume').addEventListener('input', function() {
        document.getElementById('volume-display').textContent = this.value;
    });

    // Volume slider - apply volume on change (mouse release)
    document.getElementById('system_volume').addEventListener('change', async function() {
        await applyVolume(this.value);
    });

    // Save test audio preferences when changed
    document.getElementById('test_device').addEventListener('change', saveTestAudioPreferences);
    document.getElementById('test_audio_file').addEventListener('change', saveTestAudioPreferences);

    // Auto-save ready notification sound when changed
    const readyAudioFile = document.getElementById('ready_audio_file');
    if (readyAudioFile) {
        readyAudioFile.addEventListener('change', async function() {
            const key = 'ready_audio_file';
            const value = this.value;

            console.log(`[Settings] Auto-saving ready_audio_file: ${value}`);

            // Auto-save to database (don't track as change)
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ key, value })
                });

                const data = await response.json();
                if (data.success) {
                    console.log(`[Settings] ✓ Ready notification sound saved: ${value}`);
                    showStatus('Ready notification sound saved', 'success');

                    // Update original settings to reflect save
                    originalSettings[key] = value;
                } else {
                    console.error('[Settings] Failed to save ready_audio_file:', data.error);
                    showStatus('Failed to save ready notification sound', 'danger');
                }
            } catch (error) {
                console.error('[Settings] Error auto-saving ready_audio_file:', error);
                showStatus('Error saving ready notification sound', 'danger');
            }
        });
    }

    // Auto-save distance unit when changed
    document.querySelectorAll('input[name="distance_unit"]').forEach(radio => {
        radio.addEventListener('change', async function() {
            const key = 'distance_unit';
            const value = this.value;

            console.log(`[Settings] Auto-saving distance_unit: ${value}`);

            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ key, value })
                });

                const data = await response.json();
                if (data.success) {
                    console.log(`[Settings] ✓ Distance unit saved: ${value}`);
                    showStatus(`Distance unit changed to ${value}`, 'success');

                    // Update original settings to reflect save
                    originalSettings[key] = value;
                } else {
                    console.error('[Settings] Failed to save distance_unit:', data.error);
                    showStatus('Failed to save distance unit', 'danger');
                }
            } catch (error) {
                console.error('[Settings] Error auto-saving distance_unit:', error);
                showStatus('Error saving distance unit', 'danger');
            }
        });
    });

    // Auto-save voice gender when changed
    document.querySelectorAll('input[name="voice_gender"]').forEach(radio => {
        radio.addEventListener('change', async function() {
            const key = 'voice_gender';
            const value = this.value;

            console.log(`[Settings] Auto-saving voice_gender: ${value}`);

            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ key, value })
                });

                const data = await response.json();
                if (data.success) {
                    console.log(`[Settings] ✓ Voice gender saved: ${value}`);
                    showStatus(`Voice gender changed to ${value}`, 'success');

                    // Update original settings to reflect save
                    originalSettings[key] = value;
                } else {
                    console.error('[Settings] Failed to save voice_gender:', data.error);
                    showStatus('Failed to save voice gender', 'danger');
                }
            } catch (error) {
                console.error('[Settings] Error auto-saving voice_gender:', error);
                showStatus('Error saving voice gender', 'danger');
            }
        });
    });

    // Auto-save timing defaults
    ['min_travel_time', 'max_travel_time'].forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('change', async function() {
                const key = fieldId;
                const value = this.value;

                console.log(`[Settings] Auto-saving ${key}: ${value}`);

                try {
                    const response = await fetch('/api/settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ key, value })
                    });

                    const data = await response.json();
                    if (data.success) {
                        console.log(`[Settings] ✓ ${key} saved: ${value}`);
                        showStatus(`${key.replace('_', ' ')} saved`, 'success');
                        originalSettings[key] = value;
                    } else {
                        console.error(`[Settings] Failed to save ${key}:`, data.error);
                        showStatus(`Failed to save ${key}`, 'danger');
                    }
                } catch (error) {
                    console.error(`[Settings] Error auto-saving ${key}:`, error);
                    showStatus(`Error saving ${key}`, 'danger');
                }
            });
        }
    });

    // Auto-save ready LED color
    const readyLedColor = document.getElementById('ready_led_color');
    if (readyLedColor) {
        readyLedColor.addEventListener('change', async function() {
            const key = 'ready_led_color';
            const value = this.value;

            console.log(`[Settings] Auto-saving ready_led_color: ${value}`);

            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ key, value })
                });

                const data = await response.json();
                if (data.success) {
                    console.log(`[Settings] ✓ Ready LED color saved: ${value}`);
                    showStatus(`Ready LED color changed to ${value}`, 'success');
                    originalSettings[key] = value;
                } else {
                    console.error('[Settings] Failed to save ready_led_color:', data.error);
                    showStatus('Failed to save ready LED color', 'danger');
                }
            } catch (error) {
                console.error('[Settings] Error auto-saving ready_led_color:', error);
                showStatus('Error saving ready LED color', 'danger');
            }
        });
    }

    // Auto-save network settings
    ['wifi_ssid', 'wifi_password'].forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('change', async function() {
                const key = fieldId;
                const value = this.value;

                console.log(`[Settings] Auto-saving ${key}`);

                try {
                    const response = await fetch('/api/settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ key, value })
                    });

                    const data = await response.json();
                    if (data.success) {
                        console.log(`[Settings] ✓ ${key} saved`);
                        showStatus(`${key === 'wifi_ssid' ? 'WiFi SSID' : 'WiFi password'} saved`, 'success');
                        originalSettings[key] = value;
                    } else {
                        console.error(`[Settings] Failed to save ${key}:`, data.error);
                        showStatus(`Failed to save ${key}`, 'danger');
                    }
                } catch (error) {
                    console.error(`[Settings] Error auto-saving ${key}:`, error);
                    showStatus(`Error saving ${key}`, 'danger');
                }
            });
        }
    });
}

/**
 * Confirm reset to defaults
 */
function confirmReset() {
    if (confirm('Are you sure you want to reset all settings to defaults? This cannot be undone.')) {
        resetToDefaults();
    }
}

/**
 * Reset all settings to defaults
 */
async function resetToDefaults() {
    const resetBtn = document.getElementById('reset-btn');
    resetBtn.disabled = true;
    resetBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Resetting...';

    try {
        const response = await fetch('/api/settings/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            showStatus('Settings reset to defaults. Reloading...', 'success');

            // Reload page after short delay
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showStatus('Failed to reset settings: ' + data.error, 'danger');
            resetBtn.disabled = false;
            resetBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i> Reset to Defaults';
        }
    } catch (error) {
        console.error('Error resetting settings:', error);
        showStatus('Failed to reset settings: ' + error.message, 'danger');
        resetBtn.disabled = false;
        resetBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i> Reset to Defaults';
    }
}

/**
 * Toggle password visibility
 */
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('wifi_password');
    const toggleBtn = document.getElementById('toggle-password');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.innerHTML = '<i class="bi bi-eye-slash"></i>';
    } else {
        passwordInput.type = 'password';
        toggleBtn.innerHTML = '<i class="bi bi-eye"></i>';
    }
}

/**
 * Show status message
 */
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status-message');
    statusDiv.className = `alert alert-${type}`;
    statusDiv.textContent = message;
    statusDiv.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}

/**
 * Load device status and update dropdown
 */
async function loadDeviceStatus() {
    try {
        const response = await fetch('/api/settings/devices');
        const data = await response.json();

        if (data.success && data.devices) {
            const select = document.getElementById('test_device');

            // Clear existing options
            select.innerHTML = '';

            // Add "ALL" option first
            const allOption = document.createElement('option');
            allOption.value = 'ALL';
            allOption.textContent = 'ALL (Sequential)';
            select.appendChild(allOption);

            // Add individual device options
            data.devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.device_id;

                // Simple labels: "Start", "Cone 1", "Cone 2", etc.
                if (device.status === 'offline') {
                    option.textContent = `${device.name} (Offline)`;
                    option.disabled = true;
                    option.style.color = '#999';
                } else {
                    option.textContent = device.name;
                }

                select.appendChild(option);
            });

            console.log('[Device Status] Loaded device status successfully');
        } else {
            console.error('[Device Status] Failed to load:', data.error);
        }
    } catch (error) {
        console.error('[Device Status] Exception:', error);
    }
}

// Old loadCurrentNetwork function removed - now handled by the function at line ~1797

/**
 * Play selected audio file SERVER-SIDE (through selected device speaker)
 */
async function playSelectedAudio() {
    const audioFile = document.getElementById('test_audio_file').value;
    const deviceId = document.getElementById('test_device').value;

    if (!audioFile) {
        showStatus('Please select an audio file first', 'warning');
        return;
    }

    const playBtn = document.getElementById('play-audio-btn');

    // Disable button while playing
    playBtn.disabled = true;
    playBtn.innerHTML = '<i class="bi bi-pause-fill"></i> Playing...';

    try {
        const deviceName = document.getElementById('test_device').selectedOptions[0].text;
        console.log(`[Audio Test] Playing ${audioFile} on ${deviceName}`);

        // Call server-side endpoint to play audio through selected device
        const response = await fetch('/api/settings/test-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: audioFile,
                device_id: deviceId
            })
        });

        const data = await response.json();

        if (data.success) {
            console.log(`[Audio Test] ✓ Audio playing on ${deviceName}`);
            showStatus(data.message, 'success');

            // Calculate timeout based on mode
            // Sequential mode: 6 devices × 3 seconds = 18 seconds + buffer
            // Single device: 3 seconds
            const timeout = data.mode === 'sequential' ? 20000 : 3000;

            // Re-enable button after estimated playback time
            setTimeout(() => {
                playBtn.disabled = false;
                playBtn.innerHTML = '<i class="bi bi-play-fill"></i> Play';
            }, timeout);
        } else {
            console.error('[Audio Test] Failed:', data.error);
            showStatus('Failed to play audio: ' + data.error, 'danger');
            playBtn.disabled = false;
            playBtn.innerHTML = '<i class="bi bi-play-fill"></i> Play';
        }
    } catch (error) {
        console.error('[Audio Test] Exception:', error);
        showStatus('Failed to play audio: ' + error.message, 'danger');
        playBtn.disabled = false;
        playBtn.innerHTML = '<i class="bi bi-play-fill"></i> Play';
    }
}

/**
 * Test LED color on all devices
 */
async function testLED() {
    const ledDevice = document.getElementById('test_led_device').value;
    const ledColor = document.getElementById('test_led_color').value;
    const testBtn = document.getElementById('test-led-btn');

    console.log(`[LED Test] Starting test - Device: ${ledDevice}, Color: ${ledColor}`);

    testBtn.disabled = true;
    testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';

    try {
        console.log('[LED Test] Sending POST request to /api/settings/test-led');
        const response = await fetch('/api/settings/test-led', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                color: ledColor,
                device: ledDevice
            })
        });

        console.log(`[LED Test] Response status: ${response.status}`);
        const data = await response.json();
        console.log('[LED Test] Response data:', data);

        if (data.success) {
            console.log('[LED Test] Response results:', data.results);

            // Build status message based on results
            let statusMessage = `LED test: ${ledColor} for 3 seconds`;
            if (data.results) {
                const successCount = data.results.success ? data.results.success.length : 0;
                const failedCount = data.results.failed ? data.results.failed.length : 0;
                statusMessage += ` (${successCount} succeeded, ${failedCount} failed)`;

                if (failedCount > 0) {
                    console.warn('[LED Test] Failed devices:', data.results.failed);
                }
            }

            showStatus(statusMessage, data.results && data.results.failed.length > 0 ? 'warning' : 'success');
            console.log('[LED Test] LED commands sent successfully');

            // Re-enable after 5 seconds
            setTimeout(() => {
                testBtn.disabled = false;
                testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test LED';
                console.log('[LED Test] Test complete, button re-enabled');
            }, 5500);
        } else {
            console.error('[LED Test] Failed:', data.error);
            showStatus('LED test failed: ' + (data.error || 'Unknown error'), 'danger');
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test LED';
        }
    } catch (error) {
        console.error('[LED Test] Exception:', error);
        showStatus('Failed to test LED: ' + error.message, 'danger');
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test LED';
    }
}

/**
 * Apply volume to system
 */
async function applyVolume(volume) {
    try {
        console.log(`[Volume] Setting volume to ${volume}%`);
        const response = await fetch('/api/settings/apply-volume', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ volume: parseInt(volume) })
        });

        const data = await response.json();

        if (data.success) {
            if (data.hardware_applied) {
                console.log(`[Volume] ✓ Volume set to ${volume}% (hardware applied)`);
            } else {
                console.log(`[Volume] ⚠ Volume saved to ${volume}% (no audio hardware available)`);
            }
        } else {
            console.error('[Volume] Failed to set volume:', data.error);
        }
    } catch (error) {
        console.error('[Volume] Exception:', error);
    }
}

// ============================================
// TOUCH SENSOR CALIBRATION
// ============================================

let calibrationSocket = null;
let testModeActive = false;
let selectedCalibrationDevice = null;
let liveReadingInterval = null;
let readingStreamActive = false;
let magnitudeChart = null;
let magnitudeBuffer = [];
const MAGNITUDE_BUFFER_SIZE = 10;
let readingStartTime = null;
let readingTimerInterval = null;

// Initialize calibration section when page loads
function initializeCalibration() {
    loadCalibrationDeviceStatus();
    setupCalibrationEventListeners();
    initializeCalibrationWebSocket();
    initializeMagnitudeChart();
}

function initializeMagnitudeChart() {
    const ctx = document.getElementById('magnitude-chart');
    if (!ctx) return;

    magnitudeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
            datasets: [{
                label: 'Magnitude (g)',
                data: Array(MAGNITUDE_BUFFER_SIZE).fill(0),
                backgroundColor: function(context) {
                    const value = context.parsed.y;
                    const threshold = parseFloat(document.getElementById('live-threshold-display')?.textContent) || 0;
                    return value > threshold ? 'rgba(40, 167, 69, 0.8)' : 'rgba(13, 110, 253, 0.8)';
                },
                borderColor: function(context) {
                    const value = context.parsed.y;
                    const threshold = parseFloat(document.getElementById('live-threshold-display')?.textContent) || 0;
                    return value > threshold ? 'rgb(40, 167, 69)' : 'rgb(13, 110, 253)';
                },
                borderWidth: 1,
                barThickness: 30
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 0
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Magnitude (g)',
                        font: { size: 11 }
                    },
                    ticks: {
                        font: { size: 10 }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Reading #',
                        font: { size: 11 }
                    },
                    ticks: {
                        font: { size: 10 }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Magnitude: ' + context.parsed.y.toFixed(3) + ' g';
                        }
                    }
                }
            }
        }
    });
}

function initializeCalibrationWebSocket() {
    // Connect to WebSocket namespace
    calibrationSocket = io('/calibration');

    calibrationSocket.on('connect', function() {
        console.log('[Calibration] WebSocket connected');
    });

    calibrationSocket.on('disconnect', function() {
        console.log('[Calibration] WebSocket disconnected');
        readingStreamActive = false;
    });

    // Reading stream updates
    calibrationSocket.on('reading_update', function(data) {
        updateLiveSensorReading(data);
    });

    // Calibration progress updates
    calibrationSocket.on('calibration_progress', function(data) {
        updateCalibrationProgress(data);
    });

    // Stream status
    calibrationSocket.on('stream_started', function(data) {
        console.log('[Calibration] Reading stream started for device', data.device_num);
    });

    calibrationSocket.on('stream_stopped', function(data) {
        console.log('[Calibration] Reading stream stopped');
        readingStreamActive = false;
    });

    // Errors
    calibrationSocket.on('error', function(data) {
        console.error('[Calibration] WebSocket error:', data.message);
        showCalibrationMessage('danger', 'Error: ' + data.message);
    });
}

function setupCalibrationEventListeners() {
    // Refresh status button
    const refreshBtn = document.getElementById('refresh-calibration-status-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadCalibrationDeviceStatus);
    }

    // Clear log button
    const clearLogBtn = document.getElementById('clear-log-btn');
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', clearSystemLog);
    }

    // Device selection (old UI - kept for backward compatibility)
    const deviceSelect = document.getElementById('calibration-device-select');
    if (deviceSelect) {
        deviceSelect.addEventListener('change', function(e) {
            const deviceNum = e.target.value;
            if (deviceNum) {
                selectedCalibrationDevice = parseInt(deviceNum);
                loadDeviceThreshold(selectedCalibrationDevice);
                const thresholdSection = document.getElementById('threshold-adjustment-section');
                if (thresholdSection) thresholdSection.style.display = 'block';
                startLiveReadingStream();
            } else {
                selectedCalibrationDevice = null;
                const thresholdSection = document.getElementById('threshold-adjustment-section');
                if (thresholdSection) thresholdSection.style.display = 'none';
                stopLiveReadingStream();
            }
        });
    }

    // Threshold adjustment buttons (old UI - kept for backward compatibility)
    const decreaseBtn = document.getElementById('threshold-decrease-btn');
    const increaseBtn = document.getElementById('threshold-increase-btn');
    const saveBtn = document.getElementById('threshold-save-btn');

    if (decreaseBtn) decreaseBtn.addEventListener('click', () => adjustThreshold(-0.5));
    if (increaseBtn) increaseBtn.addEventListener('click', () => adjustThreshold(0.5));
    if (saveBtn) saveBtn.addEventListener('click', saveThreshold);

    // Test mode buttons (old UI - kept for backward compatibility)
    const startTestBtn = document.getElementById('start-test-mode-btn');
    const stopTestBtn = document.getElementById('stop-test-mode-btn');

    if (startTestBtn) startTestBtn.addEventListener('click', startTestMode);
    if (stopTestBtn) stopTestBtn.addEventListener('click', stopTestMode);

    // Calibration button (old UI - kept for backward compatibility)
    const runCalBtn = document.getElementById('run-calibration-btn');
    if (runCalBtn) runCalBtn.addEventListener('click', startCalibration);

    // Apply recommended threshold (old UI - kept for backward compatibility)
    const applyRecBtn = document.getElementById('apply-recommended-btn');
    if (applyRecBtn) applyRecBtn.addEventListener('click', applyRecommendedThreshold);
}

function loadCalibrationDeviceStatus() {
    fetch('/api/calibration/devices/status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateCalibrationDeviceTable(data.devices);
                populateCalibrationDeviceSelect(data.devices);
            } else {
                showCalibrationMessage('danger', 'Error loading device status');
            }
        })
        .catch(error => {
            console.error('[Calibration] Error loading device status:', error);
            showCalibrationMessage('danger', 'Error loading device status: ' + error.message);
        });
}

function updateCalibrationDeviceTable(devices) {
    const tbody = document.querySelector('#calibration-devices-table tbody');
    if (!tbody) return;

    console.log('[Calibration] Updating device table with', devices.length, 'devices');
    tbody.innerHTML = '';

    devices.forEach(device => {
        const row = document.createElement('tr');

        // Threshold display - click to edit
        let thresholdHtml = '--';
        if (device.online && device.threshold !== undefined) {
            thresholdHtml = `
                <span class="threshold-display" data-device="${device.device_num}" onclick="editThreshold(${device.device_num}, ${device.threshold})">
                    ${device.threshold.toFixed(2)} <i class="bi bi-pencil-square text-muted small"></i>
                </span>
                <input type="number" class="form-control form-control-sm threshold-edit"
                       data-device="${device.device_num}"
                       value="${device.threshold.toFixed(2)}"
                       step="0.01"
                       style="display: none; width: 100px;"
                       onblur="saveThresholdInline(${device.device_num}, this.value)"
                       onkeypress="if(event.key==='Enter') saveThresholdInline(${device.device_num}, this.value)">
            `;
        }

        // Action buttons
        let actionsHtml = '--';
        if (device.online) {
            actionsHtml = `
                <button class="btn btn-sm btn-outline-success me-1" onclick="startTestMode(${device.device_num}, ${device.threshold})">
                    <i class="bi bi-hand-index"></i> Test
                </button>
                <button class="btn btn-sm btn-outline-info me-1" onclick="startLiveReading(${device.device_num})">
                    <i class="bi bi-activity"></i> Live Reading
                </button>
                <button class="btn btn-sm btn-outline-primary" onclick="startCalibrationForDevice(${device.device_num})">
                    <i class="bi bi-gear-fill"></i> Calibrate
                </button>
            `;
        }

        row.innerHTML = `
            <td>${device.name}</td>
            <td>
                ${device.online
                    ? '<span class="badge bg-success">Online</span>'
                    : '<span class="badge bg-secondary">Offline</span>'}
            </td>
            <td>${thresholdHtml}</td>
            <td>${actionsHtml}</td>
        `;
        tbody.appendChild(row);
    });
}

function populateCalibrationDeviceSelect(devices) {
    const select = document.getElementById('calibration-device-select');
    if (!select) return;

    select.innerHTML = '<option value="">-- Select Device --</option>';

    // Only show online devices
    devices.filter(d => d.online).forEach(device => {
        const option = document.createElement('option');
        option.value = device.device_num;
        option.textContent = device.name;
        select.appendChild(option);
    });
}

// ============================================
// SIMPLIFIED UI FUNCTIONS
// ============================================

function editThreshold(deviceNum, currentValue) {
    // Hide all other edit fields
    document.querySelectorAll('.threshold-display').forEach(el => el.style.display = 'inline');
    document.querySelectorAll('.threshold-edit').forEach(el => el.style.display = 'none');

    // Show edit field for this device
    const display = document.querySelector(`.threshold-display[data-device="${deviceNum}"]`);
    const input = document.querySelector(`.threshold-edit[data-device="${deviceNum}"]`);

    if (display && input) {
        display.style.display = 'none';
        input.style.display = 'inline-block';
        input.focus();
        input.select();
    }
}

function saveThresholdInline(deviceNum, value) {
    const threshold = parseFloat(value);

    if (isNaN(threshold) || threshold <= 0) {
        showCalibrationMessage('danger', 'Invalid threshold value');
        loadCalibrationDeviceStatus(); // Reload to reset UI
        return;
    }

    logToSystemLog(`💾 Saving threshold ${threshold.toFixed(2)} for device ${deviceNum}...`);

    fetch(`/api/calibration/device/${deviceNum}/threshold`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: threshold })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            logToSystemLog(`✅ ${data.message}`);
            showCalibrationMessage('success', data.message);

            // Update the display directly with the new value
            const display = document.querySelector(`.threshold-display[data-device="${deviceNum}"]`);
            const input = document.querySelector(`.threshold-edit[data-device="${deviceNum}"]`);

            if (display) {
                // Update the display text and onclick handler
                display.innerHTML = `${threshold.toFixed(2)} <i class="bi bi-pencil-square text-muted small"></i>`;
                display.setAttribute('onclick', `editThreshold(${deviceNum}, ${threshold})`);
                display.style.display = 'inline';
            }
            if (input) {
                input.style.display = 'none';
                input.value = threshold.toFixed(2);
            }
        } else {
            logToSystemLog(`❌ Error: ${data.error}`);
            showCalibrationMessage('danger', 'Error: ' + data.error);
            loadCalibrationDeviceStatus();
        }
    })
    .catch(error => {
        logToSystemLog(`❌ Error saving threshold: ${error.message}`);
        showCalibrationMessage('danger', 'Error saving threshold: ' + error.message);
        loadCalibrationDeviceStatus();
    });
}

function startLiveReading(deviceNum) {
    // For remote devices (1-5), enable live reading mode to get faster heartbeats
    if (deviceNum >= 1 && deviceNum <= 5) {
        fetch(`/api/calibration/device/${deviceNum}/live-reading`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled: true, duration: 10})
        }).catch(error => {
            console.error('Failed to enable live reading mode:', error);
        });
    }

    // First get the threshold for this device
    fetch(`/api/calibration/device/${deviceNum}/threshold`)
        .then(response => response.json())
        .then(thresholdData => {
            const threshold = thresholdData.success ? thresholdData.threshold : null;

            logToSystemLog(`📊 Starting live reading for device ${deviceNum} (10 seconds)...`);
            if (threshold !== null) {
                logToSystemLog(`   Threshold: ${threshold.toFixed(3)}g (touch detected if magnitude exceeds this)`);
            }
            logToSystemLog(``);

            let count = 0;
            const maxReadings = deviceNum === 0 ? 100 : 50; // 10s @ 10Hz for Device 0, 10s @ 5Hz for others

            function readSensor() {
                if (count >= maxReadings) {
                    logToSystemLog(``);
                    logToSystemLog(`✅ Live reading complete for device ${deviceNum}`);
                    return;
                }

                fetch(`/api/calibration/device/${deviceNum}/reading`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const mag = data.magnitude;
                            const touchDetected = threshold !== null && mag >= threshold;
                            const indicator = touchDetected ? '🎯 TOUCH!' : '';
                            const line = `[${count + 1}] Mag: ${mag.toFixed(3)}g | X: ${data.x.toFixed(3)}g | Y: ${data.y.toFixed(3)}g | Z: ${data.z.toFixed(3)}g ${indicator}`;
                            logToSystemLog(line);
                            count++;
                            setTimeout(readSensor, 100); // 10Hz
                        } else {
                            logToSystemLog(`❌ Error reading sensor: ${data.error}`);
                        }
                    })
                    .catch(error => {
                        logToSystemLog(`❌ Error: ${error.message}`);
                    });
            }

            readSensor();
        })
        .catch(error => {
            logToSystemLog(`❌ Error getting threshold: ${error.message}`);
        });
}

function startCalibrationForDevice(deviceNum) {
    if (!confirm('Calibration takes about 1 minute.\n\n1. Click OK to start\n2. Wait 3 seconds\n3. START TAPPING THE DEVICE 5 times (30 seconds total)\n4. Tap every 5-6 seconds\n5. Auto-adjusts if no taps detected\n\nContinue?')) {
        return;
    }

    logToSystemLog('\n' + '='.repeat(60));
    logToSystemLog(`🎯 Starting calibration for device ${deviceNum}...`);
    logToSystemLog('='.repeat(60));

    if (calibrationSocket) {
        calibrationSocket.emit('start_calibration_wizard', {
            device_num: deviceNum,
            tap_count: 5
        });
    } else {
        logToSystemLog('❌ Error: WebSocket not connected');
        showCalibrationMessage('danger', 'WebSocket not connected');
    }
}

function logToSystemLog(message) {
    const logContent = document.getElementById('calibration-log-content');
    if (!logContent) return;

    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.textContent = `[${timestamp}] ${message}`;
    logContent.appendChild(line);

    // Auto-scroll to bottom
    const logContainer = document.getElementById('calibration-system-log');
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

function clearSystemLog() {
    const logContent = document.getElementById('calibration-log-content');
    if (logContent) {
        logContent.innerHTML = '<div class="text-muted">Ready. Waiting for actions...</div>';
    }
}

function selectDeviceForCalibration(deviceNum) {
    const select = document.getElementById('calibration-device-select');
    if (select) {
        select.value = deviceNum;
        select.dispatchEvent(new Event('change'));
    }
}

function loadDeviceThreshold(deviceNum) {
    fetch(`/api/calibration/device/${deviceNum}/threshold`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const input = document.getElementById('threshold-input');
                const display = document.getElementById('live-threshold-display');
                if (input) input.value = data.threshold.toFixed(2);
                if (display) display.textContent = data.threshold.toFixed(2);
            }
        })
        .catch(error => {
            console.error('[Calibration] Error loading threshold:', error);
        });
}

function adjustThreshold(delta) {
    const input = document.getElementById('threshold-input');
    if (!input) return;

    const currentValue = parseFloat(input.value) || 0;
    const newValue = Math.max(0, currentValue + delta);
    input.value = newValue.toFixed(2);
}

function saveThreshold() {
    if (selectedCalibrationDevice === null) return;

    const input = document.getElementById('threshold-input');
    if (!input) return;

    const threshold = parseFloat(input.value);

    fetch(`/api/calibration/device/${selectedCalibrationDevice}/threshold`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: threshold })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCalibrationMessage('success', data.message);
            const display = document.getElementById('live-threshold-display');
            if (display) display.textContent = threshold.toFixed(2);

            // Refresh device status table after a short delay to ensure backend has updated
            console.log('[Calibration] Threshold saved, refreshing device table...');
            setTimeout(() => {
                loadCalibrationDeviceStatus();
            }, 500);
        } else {
            showCalibrationMessage('danger', 'Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('[Calibration] Error saving threshold:', error);
        showCalibrationMessage('danger', 'Error saving threshold: ' + error.message);
    });
}

function startLiveReadingStream() {
    if (readingStreamActive) {
        stopLiveReadingStream(); // Clear any existing stream
    }

    // Clear buffer for new device
    magnitudeBuffer = [];
    readingStartTime = Date.now();

    // Update timer display
    const timerDisplay = document.getElementById('reading-timer');
    if (timerDisplay) {
        timerDisplay.textContent = '0s';
    }

    // Start timer that updates display and auto-stops after 30s
    readingTimerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - readingStartTime) / 1000);
        if (timerDisplay) {
            timerDisplay.textContent = elapsed + 's';
        }

        // Auto-stop after 30 seconds
        if (elapsed >= 30) {
            stopLiveReadingStream();
            if (timerDisplay) {
                timerDisplay.textContent = '30s (stopped)';
            }
        }
    }, 1000);

    if (selectedCalibrationDevice !== null && calibrationSocket) {
        calibrationSocket.emit('start_reading_stream', { device_num: selectedCalibrationDevice });
        readingStreamActive = true;
    }
}

function stopLiveReadingStream() {
    if (calibrationSocket && readingStreamActive) {
        calibrationSocket.emit('stop_reading_stream', {});
        readingStreamActive = false;
    }

    // Clear timer
    if (readingTimerInterval) {
        clearInterval(readingTimerInterval);
        readingTimerInterval = null;
    }
}

function updateLiveSensorReading(data) {
    if (!data.success) return;

    const magnitudeDisplay = document.getElementById('live-magnitude-display');
    const thresholdDisplay = document.getElementById('live-threshold-display');

    if (!magnitudeDisplay) return;

    const magnitude = data.magnitude;
    const threshold = parseFloat(thresholdDisplay?.textContent) || 0;

    // Update current magnitude display
    magnitudeDisplay.textContent = magnitude.toFixed(3);

    // Add to buffer (keep last 10 readings)
    magnitudeBuffer.push(magnitude);
    if (magnitudeBuffer.length > MAGNITUDE_BUFFER_SIZE) {
        magnitudeBuffer.shift(); // Remove oldest
    }

    // Update chart
    if (magnitudeChart) {
        // Pad with zeros if buffer not full yet
        const chartData = [...magnitudeBuffer];
        while (chartData.length < MAGNITUDE_BUFFER_SIZE) {
            chartData.unshift(0);
        }

        magnitudeChart.data.datasets[0].data = chartData;

        // Update Y-axis scale
        const maxValue = Math.max(threshold * 1.5, Math.max(...chartData), 1);
        magnitudeChart.options.scales.y.max = maxValue;

        magnitudeChart.update('none');
    }
}

function startTestMode() {
    if (selectedCalibrationDevice === null) return;

    const input = document.getElementById('threshold-input');
    if (!input) return;

    const threshold = parseFloat(input.value);

    // Stop regular streaming if active
    if (readingStreamActive) {
        stopLiveReadingStream();
    }
    testModeActive = true;

    fetch(`/api/calibration/device/${selectedCalibrationDevice}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: threshold, duration: 30 })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const startBtn = document.getElementById('start-test-mode-btn');
            const stopBtn = document.getElementById('stop-test-mode-btn');
            if (startBtn) startBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-block';
            showCalibrationMessage('info', 'Test mode active - tap the device to hear beep');
        } else {
            showCalibrationMessage('danger', 'Error starting test mode: ' + data.error);
        }
    })
    .catch(error => {
        console.error('[Calibration] Error starting test mode:', error);
        showCalibrationMessage('danger', 'Error starting test mode: ' + error.message);
    });
}

function stopTestMode() {
    if (selectedCalibrationDevice === null) return;

    // Update UI immediately
    testModeActive = false;
    const startBtn = document.getElementById('start-test-mode-btn');
    const stopBtn = document.getElementById('stop-test-mode-btn');
    if (startBtn) startBtn.style.display = 'inline-block';
    if (stopBtn) stopBtn.style.display = 'none';

    fetch(`/api/calibration/device/${selectedCalibrationDevice}/test/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCalibrationMessage('success', 'Test mode stopped');
        } else {
            showCalibrationMessage('warning', 'Test mode stopped (device may not have responded)');
        }

        // Resume regular streaming
        startLiveReadingStream();
    })
    .catch(error => {
        console.error('[Calibration] Error stopping test mode:', error);
        showCalibrationMessage('warning', 'Test mode stopped locally');

        // Resume regular streaming even if stop command failed
        startLiveReadingStream();
    });
}

function startCalibration() {
    if (selectedCalibrationDevice === null) return;

    // Stop test mode if it's active
    if (testModeActive) {
        stopTestMode();
    }

    if (!confirm('Calibration takes 2-3 minutes.\n\n1. Click OK to start\n2. Wait 3 seconds\n3. Start tapping the device repeatedly\n4. Keep tapping every few seconds until calibration completes\n\nContinue?')) {
        return;
    }

    const progressSection = document.getElementById('calibration-progress-section');
    const resultsSection = document.getElementById('calibration-results-section');
    const progressBar = document.getElementById('calibration-progress-bar');
    const statusText = document.getElementById('calibration-status-text');
    const runBtn = document.getElementById('run-calibration-btn');

    if (progressSection) progressSection.style.display = 'block';
    if (resultsSection) resultsSection.style.display = 'none';
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
    }
    if (statusText) statusText.textContent = 'Starting calibration...';
    if (runBtn) runBtn.disabled = true;

    // Stop live reading stream and start calibration
    if (readingStreamActive) {
        stopLiveReadingStream();
    }

    calibrationSocket.emit('start_calibration_wizard', {
        device_num: selectedCalibrationDevice,
        tap_count: 5
    });
}

function updateCalibrationProgress(data) {
    // Log progress to system log
    switch(data.status) {
        case 'progress':
            // Real-time line-by-line streaming
            if (data.message) {
                logToSystemLog(data.message);
            }
            break;

        case 'baseline':
            logToSystemLog('📊 ' + data.message);
            break;

        case 'waiting_for_tap':
            logToSystemLog(`👆 Waiting for tap ${data.tap_number}/5...`);
            if (data.message) {
                logToSystemLog('   ' + data.message);
            }
            break;

        case 'analyzing':
            logToSystemLog('🔍 ' + data.message);
            break;

        case 'complete':
            logToSystemLog(data.message);
            logToSystemLog('='.repeat(60));

            showCalibrationMessage('success', '✅ Calibration PASSED');

            // Refresh device table to show new threshold
            setTimeout(() => loadCalibrationDeviceStatus(), 1000);
            break;

        case 'error':
            logToSystemLog(data.message);
            logToSystemLog('='.repeat(60));
            showCalibrationMessage('danger', '❌ Calibration FAILED');
            break;
    }

    // Also update old UI elements if they exist (backward compatibility)
    const statusText = document.getElementById('calibration-status-text');
    const progressBar = document.getElementById('calibration-progress-bar');
    const detailsText = document.getElementById('calibration-details');

    if (statusText || progressBar || detailsText) {
        switch(data.status) {
            case 'baseline':
                if (statusText) statusText.textContent = 'Measuring baseline...';
                if (progressBar) progressBar.style.width = '20%';
                if (detailsText) detailsText.textContent = data.message;
                break;

            case 'waiting_for_tap':
                if (statusText) statusText.textContent = `Waiting for tap ${data.tap_number}/5...`;
                const progress = 20 + (data.tap_number * 12);
                if (progressBar) progressBar.style.width = progress + '%';
                if (detailsText) detailsText.textContent = data.message;
                break;

            case 'analyzing':
                if (statusText) statusText.textContent = 'Analyzing results...';
                if (progressBar) progressBar.style.width = '90%';
                if (detailsText) detailsText.textContent = data.message;
                break;

            case 'complete':
                if (statusText) statusText.textContent = 'Calibration complete!';
                if (progressBar) {
                    progressBar.style.width = '100%';
                    progressBar.classList.add('bg-success');
                }

                setTimeout(() => {
                    const progressSection = document.getElementById('calibration-progress-section');
                    if (progressSection) progressSection.style.display = 'none';
                    showCalibrationResults(data);
                }, 1000);
                break;

            case 'error':
                if (statusText) statusText.textContent = 'Calibration failed';
                if (progressBar) progressBar.classList.add('bg-danger');
                if (detailsText) detailsText.textContent = data.error || 'Unknown error';
                const runBtn = document.getElementById('run-calibration-btn');
                if (runBtn) runBtn.disabled = false;
                break;
        }
    }
}

function showCalibrationResults(data) {
    const resultsSection = document.getElementById('calibration-results-section');
    const recommendedThreshold = document.getElementById('recommended-threshold');
    const calibrationSummary = document.getElementById('calibration-summary');
    const runBtn = document.getElementById('run-calibration-btn');

    if (resultsSection) resultsSection.style.display = 'block';
    if (recommendedThreshold) recommendedThreshold.textContent = data.recommended_threshold.toFixed(2);
    if (calibrationSummary) {
        calibrationSummary.textContent =
            `Baseline: ${data.baseline.toFixed(3)}, Tap magnitudes: ${data.tap_magnitudes.map(t => t.toFixed(3)).join(', ')}`;
    }
    if (runBtn) runBtn.disabled = false;
}

function applyRecommendedThreshold() {
    const recommendedThreshold = document.getElementById('recommended-threshold');
    const input = document.getElementById('threshold-input');

    if (recommendedThreshold && input) {
        const recommendedValue = parseFloat(recommendedThreshold.textContent);
        input.value = recommendedValue.toFixed(2);
        saveThreshold();
    }
}

function showCalibrationMessage(type, message) {
    const statusMsg = document.getElementById('calibration-status-message');
    if (!statusMsg) return;

    const iconMap = {
        'success': 'check-circle',
        'danger': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle'
    };

    statusMsg.className = `alert alert-${type}`;
    statusMsg.innerHTML = `<i class="bi bi-${iconMap[type] || 'info-circle'}"></i> ${message}`;
    statusMsg.style.display = 'block';

    setTimeout(() => {
        statusMsg.style.display = 'none';
    }, 5000);
}

// ============================================
// TEST MODE - Show touch detections in real-time
// ============================================

// Reuse existing testModeActive variable declared at line 757
let testModeDeviceNum = null;
let testModeTimeout = null;
let testModeTouchCount = 0;

function startTestMode(deviceNum, threshold) {
    if (testModeActive) {
        appendToCalibrationLog('⚠ Test mode already running. Please wait...');
        return;
    }

    const deviceInfo = ['Start', 'Cone 1', 'Cone 2', 'Cone 3', 'Cone 4', 'Cone 5'][deviceNum];

    testModeActive = true;
    testModeDeviceNum = deviceNum;
    testModeTouchCount = 0;

    clearCalibrationLog();
    appendToCalibrationLog(`========================================`);
    appendToCalibrationLog(`🧪 TEST MODE: ${deviceInfo} (Device ${deviceNum})`);
    appendToCalibrationLog(`========================================`);
    appendToCalibrationLog(`Threshold: ${threshold.toFixed(3)}g`);
    appendToCalibrationLog(`Duration: 30 seconds`);
    appendToCalibrationLog(``);
    appendToCalibrationLog(`👉 TAP the device now!`);
    appendToCalibrationLog(`   Each touch will be logged below...`);
    appendToCalibrationLog(``);

    // Start test mode on backend
    fetch(`/api/calibration/device/${deviceNum}/test-mode`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            enabled: true,
            threshold: threshold,
            duration: 30
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            appendToCalibrationLog(`✓ Test mode started`);
            appendToCalibrationLog(``);
        } else {
            appendToCalibrationLog(`❌ Error: ${data.error || 'Failed to start test mode'}`);
            testModeActive = false;
        }
    })
    .catch(error => {
        appendToCalibrationLog(`❌ Error: ${error.message}`);
        testModeActive = false;
    });

    // Poll for touch events every 500ms
    let lastTouchCount = 0;
    const pollInterval = setInterval(() => {
        if (!testModeActive) {
            clearInterval(pollInterval);
            return;
        }

        // Fetch current touch count from backend
        fetch(`/api/calibration/device/${deviceNum}/touch-count`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const currentCount = data.touch_count || 0;

                    // Only update if count increased
                    if (currentCount > lastTouchCount) {
                        const newTouches = currentCount - lastTouchCount;
                        for (let i = 0; i < newTouches; i++) {
                            testModeTouchCount++;
                            appendToCalibrationLog(`👆 Touch #${testModeTouchCount} detected!`);
                        }
                        lastTouchCount = currentCount;
                    }
                }
            })
            .catch(error => {
                // Silently ignore polling errors to avoid log spam
                console.error('Touch count poll error:', error);
            });
    }, 500);

    // Auto-stop after 30 seconds
    testModeTimeout = setTimeout(() => {
        stopTestMode();
        appendToCalibrationLog(``);
        appendToCalibrationLog(`========================================`);
        appendToCalibrationLog(`✓ TEST COMPLETE`);
        appendToCalibrationLog(`========================================`);
        appendToCalibrationLog(`Total touches detected: ${testModeTouchCount}`);
        appendToCalibrationLog(``);

        if (testModeTouchCount === 0) {
            appendToCalibrationLog(`❌ No touches detected!`);
            appendToCalibrationLog(`   → Threshold may be too HIGH (not sensitive enough)`);
            appendToCalibrationLog(`   → Try lowering threshold or tapping harder`);
        } else if (testModeTouchCount < 3) {
            appendToCalibrationLog(`⚠ Very few touches detected`);
            appendToCalibrationLog(`   → Threshold might be too high`);
        } else if (testModeTouchCount > 15) {
            appendToCalibrationLog(`⚠ Many touches detected (more than taps)`);
            appendToCalibrationLog(`   → Threshold may be too LOW (too sensitive)`);
            appendToCalibrationLog(`   → Try raising threshold`);
        } else {
            appendToCalibrationLog(`✓ Good! Threshold seems appropriate`);
        }

        clearInterval(pollInterval);
    }, 30000);
}

function stopTestMode() {
    if (!testModeActive) return;

    testModeActive = false;

    if (testModeTimeout) {
        clearTimeout(testModeTimeout);
        testModeTimeout = null;
    }

    // Stop test mode on backend
    if (testModeDeviceNum !== null) {
        fetch(`/api/calibration/device/${testModeDeviceNum}/test-mode`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled: false})
        });
    }

    testModeDeviceNum = null;
}

// Listen for touch events from WebSocket (if Device 0) or backend polling (Devices 1-5)
// This would be enhanced with actual WebSocket integration
// For now, we rely on the backend's test mode beeping

function clearCalibrationLog() {
    const logContent = document.getElementById('calibration-log-content');
    if (logContent) {
        logContent.innerHTML = '';
    }
}

function appendToCalibrationLog(message) {
    const logContent = document.getElementById('calibration-log-content');
    if (!logContent) return;

    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.textContent = `[${timestamp}] ${message}`;
    logContent.appendChild(line);

    // Auto-scroll to bottom
    const logContainer = document.getElementById('calibration-system-log');
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

/**
 * Load current network status
 */
async function loadCurrentNetwork() {
    console.log('[Settings] Loading network status...');
    try {
        const response = await fetch('/api/network/status');
        const data = await response.json();
        console.log('[Settings] Network status:', data);

        // Update the network mode description (Settings section)
        const description = document.getElementById('networkModeDescription');
        const ipAddressDiv = document.getElementById('networkIpAddress');
        const ipAddressValue = document.getElementById('networkIpAddressValue');

        if (description && data.message) {
            description.textContent = data.message;

            // Extract IP address from message (format: "Connected via Ethernet (192.168.7.116)")
            const ipMatch = data.message.match(/\((\d+\.\d+\.\d+\.\d+)\)/);
            if (ipMatch && ipAddressDiv && ipAddressValue) {
                ipAddressValue.textContent = ipMatch[1];
                ipAddressDiv.style.display = 'block';
            } else if (ipAddressDiv) {
                ipAddressDiv.style.display = 'none';
            }
        }

        // Also update the current-ssid element (Network Configuration section)
        const ssidElement = document.getElementById('current-ssid');
        if (ssidElement && data.message) {
            // Determine connection type and icon
            let icon = '';
            let colorClass = '';
            let displayText = '';

            if (data.message.includes('Ethernet')) {
                icon = '<i class="bi bi-ethernet text-success"></i> ';
                colorClass = 'text-success';
                displayText = data.message;
            } else if (data.message.includes('WiFi')) {
                icon = '<i class="bi bi-wifi text-primary"></i> ';
                colorClass = 'text-primary';
                displayText = data.message;
            } else {
                icon = '<i class="bi bi-question-circle text-muted"></i> ';
                colorClass = 'text-muted';
                displayText = data.message || 'Unknown';
            }

            ssidElement.innerHTML = `${icon}<span class="${colorClass}">${displayText}</span>`;
            console.log(`[Settings] ✓ Updated current-ssid: ${displayText}`);
        }
    } catch (error) {
        console.error('[Settings] Error loading network status:', error);
        const ssidElement = document.getElementById('current-ssid');
        if (ssidElement) {
            ssidElement.innerHTML = '<i class="bi bi-exclamation-triangle text-danger"></i> <span class="text-danger">Error loading</span>';
        }
    }
}

// Add calibration initialization to existing DOMContentLoaded
const originalDOMContentLoaded = document.addEventListener;
document.addEventListener('DOMContentLoaded', function() {
    // Initialize calibration after a short delay to ensure other systems are ready
    setTimeout(() => {
        initializeCalibration();
    }, 500);
});
