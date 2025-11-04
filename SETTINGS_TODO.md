# Settings Page TODO

## Outstanding Issues

### 1. Volume Control - Hardware Limitation
**Status**: Not Working
**Priority**: Medium

**Problem**:
The Raspberry Pi has no software-controllable volume mixer. The system has:
- HifiBerry DAC (card 0) - Hardware DAC with fixed output, no mixer controls
- HDMI audio (card 1) - Also no mixer controls
- Neither supports `amixer` volume control

**Current Behavior**:
- Volume slider saves to database
- Backend gracefully handles missing hardware (returns `hardware_applied: false`)
- No actual volume change occurs

**Solutions**:
1. Remove volume control from Settings page (accept hardware limitation)
2. Use different audio hardware (USB audio device with mixer support)
3. Implement software volume control (ALSA plugins or PulseAudio)
4. Change to informational note: "Volume control requires compatible audio hardware"

---

### 2. LED Test Button - Device Client Implementation
**Status**: Partially Working
**Priority**: High

**Problem**:
LED test commands are sent successfully from gateway but physical LEDs don't light up on field devices.

**Current Behavior**:
- ✅ All 5 field devices (192.168.99.101-105) are connected via TCP
- ✅ Gateway sends LED commands: `{"cmd": "led", "pattern": "solid_red"}`
- ✅ Backend returns success
- ❌ Physical LEDs don't light up

**Investigation Needed**:
1. Check field device client code - does it handle `{"cmd": "led"}` commands?
2. Verify if devices need to be in "Ready" or "Active" state (not "Standby")
3. Test if LEDs work during actual course deployment/activation
4. Check device logs for LED command receipt

**Diagnostic Logging Added**:
- Server-side: Detailed device status, connection info, command results
- Client-side: Console logging with `[LED Test]` prefix
- Check `/tmp/field_trainer_output.log` for server output

---

## Implementation Summary

### Completed Features ✅

1. **Database Schema** (`field_trainer/db_manager.py`)
   - Settings table with key-value storage
   - Default values initialization
   - Unique constraint on setting keys

2. **Settings Manager** (`field_trainer/settings_manager.py`)
   - CRUD operations for settings
   - Audio file scanning from `/opt/field_trainer/audio/`
   - Device online checking
   - Reset to defaults functionality

3. **Flask Routes** (`coach_interface.py`)
   - `GET /settings` - Settings page
   - `GET /api/settings` - Load all settings and audio files
   - `POST /api/settings` - Save individual setting
   - `POST /api/settings/reset` - Reset to defaults
   - `GET /api/settings/network-info` - Current WiFi SSID
   - `GET /audio/<filename>` - Serve audio files
   - `POST /api/settings/test-led` - LED test with detailed results
   - `POST /api/settings/apply-volume` - Volume control (graceful degradation)

4. **Settings Page UI** (`field_trainer/templates/settings.html`)
   - Display & Units: Distance unit (yards/meters/feet)
   - Audio Settings: Voice gender, system volume, ready notification with play button
   - Timing Defaults: Min/max travel time (per-action timing noted as future feature)
   - LED Settings: Ready LED color with test button, ready audio target
   - Network Configuration: WiFi SSID/password with current network display
   - Auto-save detection with Save/Reset buttons
   - Password visibility toggle

5. **Client-Side Logic** (`field_trainer/static/js/settings.js`)
   - Change tracking and auto-save detection
   - Audio file playback from `/audio/` directory
   - Network info loading with `iwgetid -r`
   - Comprehensive console logging for debugging
   - LED test with device success/failure reporting

---

## Testing Notes

- Settings save/load: ✅ Working
- Audio file dropdown: ✅ Working
- Audio playback: ✅ Working
- Network info display: ✅ Working
- Change detection: ✅ Working
- Volume control: ⚠️ Hardware limitation (saves but doesn't apply)
- LED test: ⚠️ Commands sent but LEDs don't activate

---

## Future Enhancements

1. **Action-Specific Timing** - Per-action min/max travel times (currently global)
2. **Device-Specific Settings** - Individual thresholds per device
3. **Calibration Tools** - Touch sensor calibration wizard
4. **System Tuning** - Performance optimization settings
5. **Backup/Restore** - Export/import settings configuration
