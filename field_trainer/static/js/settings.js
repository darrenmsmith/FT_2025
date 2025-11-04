/**
 * Settings Page JavaScript
 * Handles loading, saving, and resetting system settings
 */

// State
let originalSettings = {};
let changedSettings = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    attachEventListeners();
});

/**
 * Load all settings from API
 */
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        if (!data.success) {
            showStatus('Error loading settings: ' + data.error, 'danger');
            return;
        }

        originalSettings = { ...data.settings };
        populateSettings(data.settings);
        populateAudioFiles(data.audio_files);
        loadCurrentNetwork();

        console.log('Settings loaded successfully');
    } catch (error) {
        console.error('Error loading settings:', error);
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

    // Ready audio file dropdown
    const audioFile = settings.ready_audio_file || '';
    document.getElementById('ready_audio_file').value = audioFile;

    // Timing defaults
    document.getElementById('min_travel_time').value = settings.min_travel_time || '1';
    document.getElementById('max_travel_time').value = settings.max_travel_time || '15';

    // Device behavior
    document.getElementById('ready_led_color').value = settings.ready_led_color || 'orange';
    document.getElementById('ready_audio_target').value = settings.ready_audio_target || 'all';

    // Network configuration
    document.getElementById('wifi_ssid').value = settings.wifi_ssid || '';
    document.getElementById('wifi_password').value = settings.wifi_password || '';
}

/**
 * Populate audio files dropdown
 */
function populateAudioFiles(files) {
    const select = document.getElementById('ready_audio_file');

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
    } else {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No audio files found';
        option.disabled = true;
        select.appendChild(option);
    }
}

/**
 * Attach event listeners to all form inputs
 */
function attachEventListeners() {
    // Track changes on all setting inputs
    document.querySelectorAll('.setting-input').forEach(input => {
        if (input.type === 'radio') {
            input.addEventListener('change', function() {
                trackChange(this.dataset.setting, this.value);
            });
        } else if (input.type === 'range') {
            input.addEventListener('input', function() {
                document.getElementById('volume-display').textContent = this.value;
                trackChange(this.dataset.setting, this.value);
            });
        } else {
            input.addEventListener('change', function() {
                trackChange(this.dataset.setting, this.value);
            });
        }
    });

    // Save button
    document.getElementById('save-btn').addEventListener('click', saveAllSettings);

    // Reset button
    document.getElementById('reset-btn').addEventListener('click', confirmReset);

    // Password toggle
    document.getElementById('toggle-password').addEventListener('click', togglePasswordVisibility);

    // Play audio button
    document.getElementById('play-audio-btn').addEventListener('click', playSelectedAudio);

    // LED test button
    document.getElementById('test-led-btn').addEventListener('click', testLED);

    // Volume slider - add change event for mouse release AND apply volume
    document.getElementById('system_volume').addEventListener('change', async function() {
        trackChange(this.dataset.setting, this.value);
        // Apply volume immediately
        await applyVolume(this.value);
    });
}

/**
 * Track changes to settings
 */
function trackChange(key, value) {
    // Check if value different from original
    if (originalSettings[key] !== value) {
        changedSettings[key] = value;
    } else {
        delete changedSettings[key];
    }

    // Show/hide save button based on changes
    const hasChanges = Object.keys(changedSettings).length > 0;
    document.getElementById('action-buttons').style.display = hasChanges ? 'block' : 'none';
}

/**
 * Save all changed settings
 */
async function saveAllSettings() {
    const saveBtn = document.getElementById('save-btn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';

    try {
        let allSuccess = true;

        // Save each changed setting
        for (const [key, value] of Object.entries(changedSettings)) {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ key, value })
            });

            const data = await response.json();
            if (!data.success) {
                console.error(`Failed to save ${key}:`, data.error);
                allSuccess = false;
            }
        }

        if (allSuccess) {
            showStatus('Settings saved successfully', 'success');

            // Update original settings
            originalSettings = { ...originalSettings, ...changedSettings };
            changedSettings = {};

            // Hide save button
            document.getElementById('action-buttons').style.display = 'none';
        } else {
            showStatus('Some settings failed to save', 'warning');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showStatus('Failed to save settings: ' + error.message, 'danger');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="bi bi-check-circle"></i> Save Settings';
    }
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
 * Load current network SSID
 */
async function loadCurrentNetwork() {
    try {
        const response = await fetch('/api/settings/network-info');
        const data = await response.json();

        if (data.success && data.ssid) {
            document.getElementById('current-ssid').textContent = data.ssid;
        } else {
            document.getElementById('current-ssid').textContent = 'Unknown';
        }
    } catch (error) {
        console.error('Error loading network info:', error);
        document.getElementById('current-ssid').textContent = 'Error loading';
    }
}

/**
 * Play selected audio file
 */
function playSelectedAudio() {
    const audioFile = document.getElementById('ready_audio_file').value;

    if (!audioFile) {
        showStatus('Please select an audio file first', 'warning');
        return;
    }

    // Create audio element and play - use correct path to audio directory
    const audio = new Audio(`/audio/${audioFile}`);
    const playBtn = document.getElementById('play-audio-btn');

    // Disable button while playing
    playBtn.disabled = true;
    playBtn.innerHTML = '<i class="bi bi-pause-fill"></i> Playing...';

    audio.play().catch(error => {
        console.error('Error playing audio:', error);
        showStatus('Failed to play audio: ' + error.message, 'danger');
        playBtn.disabled = false;
        playBtn.innerHTML = '<i class="bi bi-play-fill"></i> Play';
    });

    audio.onended = () => {
        playBtn.disabled = false;
        playBtn.innerHTML = '<i class="bi bi-play-fill"></i> Play';
    };
}

/**
 * Test LED color on all devices
 */
async function testLED() {
    const ledColor = document.getElementById('ready_led_color').value;
    const testBtn = document.getElementById('test-led-btn');

    console.log(`[LED Test] Starting test with color: ${ledColor}`);

    testBtn.disabled = true;
    testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';

    try {
        console.log('[LED Test] Sending POST request to /api/settings/test-led');
        const response = await fetch('/api/settings/test-led', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ color: ledColor })
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

            // Re-enable after 3 seconds
            setTimeout(() => {
                testBtn.disabled = false;
                testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test';
                console.log('[LED Test] Test complete, button re-enabled');
            }, 3500);
        } else {
            console.error('[LED Test] Failed:', data.error);
            showStatus('LED test failed: ' + (data.error || 'Unknown error'), 'danger');
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test';
        }
    } catch (error) {
        console.error('[LED Test] Exception:', error);
        showStatus('Failed to test LED: ' + error.message, 'danger');
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="bi bi-lightbulb"></i> Test';
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
