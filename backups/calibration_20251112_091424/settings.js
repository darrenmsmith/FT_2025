/**
 * Settings Page JavaScript
 * Handles loading and auto-saving system settings
 */

// State
let originalSettings = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    loadDeviceStatus();
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

/**
 * Load current network SSID
 */
async function loadCurrentNetwork() {
    console.log('[Network] Loading current network info...');
    try {
        const response = await fetch('/api/settings/network-info');
        console.log('[Network] API response status:', response.status);

        const data = await response.json();
        console.log('[Network] API data:', data);

        const ssidElement = document.getElementById('current-ssid');
        if (!ssidElement) {
            console.error('[Network] Element not found: current-ssid');
            return;
        }

        if (data.success && data.ssid) {
            ssidElement.textContent = data.ssid;
            console.log(`[Network] ✓ Set SSID to: ${data.ssid}`);
        } else {
            ssidElement.textContent = 'Unknown';
            console.warn('[Network] No SSID in response');
        }
    } catch (error) {
        console.error('[Network] Exception:', error);
        const ssidElement = document.getElementById('current-ssid');
        if (ssidElement) {
            ssidElement.textContent = 'Error loading';
        }
    }
}

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
