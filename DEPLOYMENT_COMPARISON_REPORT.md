# Field Trainer Deployment Comparison Report

**Generated:** 2025-11-27
**Comparing:** `deploy_scripts` repository vs `FT_2025` application requirements

---

## Executive Summary

After analyzing both the deployment scripts and the Field Trainer application code, I found **several critical missing dependencies** that will cause the application to fail or have limited functionality after a fresh deployment.

### Critical Issues Found: 3
### Non-Critical Issues: 4
### Configuration Issues: 2

---

## Critical Missing Dependencies

### 1. **mpg123** - MP3 Audio Playback (CRITICAL)

**Status:** NOT INSTALLED by deployment scripts
**Impact:** Audio playback will completely fail
**Used in:** `audio_manager.py:164-170`

```python
# audio_manager.py uses mpg123 for MP3 playback
cmd = [
    'mpg123',
    '-q',  # Quiet mode
    '-a', 'default',  # Use default ALSA device (I2S)
    '-f', str(volume_scale),  # Volume control
    str(audio_path)
]
```

**Fix:** Add to `phase3_packages.sh`:
```bash
UTIL_PACKAGES=(
    "git"
    "curl"
    "mpg123"   # ADD THIS - Required for MP3 playback
)
```

---

### 2. **alsa-utils** - Audio Device Management (CRITICAL)

**Status:** NOT INSTALLED by deployment scripts
**Impact:** Audio device verification fails, speaker-test unavailable
**Used in:** `audio_manager.py:84, 226-230`

```python
# Verifying audio device
result = subprocess.run(['aplay', '-L'], ...)

# Fallback beep generation
subprocess.run(['speaker-test', '-t', 'sine', '-f', '1000', ...])
```

**Fix:** Add to `phase3_packages.sh`:
```bash
UTIL_PACKAGES=(
    "git"
    "curl"
    "mpg123"
    "alsa-utils"   # ADD THIS - Provides aplay, speaker-test
)
```

---

### 3. **requests** (Python pip package) - HTTP Client

**Status:** NOT INSTALLED by deployment scripts
**Impact:** Test scripts fail, may affect future API features
**Used in:** `test_team_management.py`, `test_api_integration.py`

```python
import requests
```

**Fix:** Add to `phase3_packages.sh` pip section:
```bash
# Install requests (for API testing)
pip3 install requests --break-system-packages
```

---

## Non-Critical Missing Dependencies

### 4. **psutil** (Python pip package) - System Monitoring

**Status:** NOT INSTALLED
**Impact:** `test_load_stress.py` will fail (test file only)
**Used in:** `test_load_stress.py:12`

**Fix (optional):**
```bash
pip3 install psutil --break-system-packages
```

---

### 5. Development Tools (pytest, flake8, black)

**Status:** Listed in `requirements.txt` but NOT installed by deployment
**Impact:** Cannot run tests on deployed device
**Recommendation:** Keep as-is for production; add separate dev setup script if needed

---

## Dependency Comparison Table

| Dependency | Field Trainer Uses | Deploy Scripts Install | Status |
|------------|-------------------|----------------------|--------|
| **APT Packages** | | | |
| python3 | Yes | Yes (phase3) | OK |
| python3-pip | Yes | Yes (phase3) | OK |
| python3-flask | Yes | Yes (phase3) | OK |
| python3-pil | Yes | Yes (phase3) | OK |
| python3-smbus | Yes | Yes (phase3) | OK |
| python3-dev | Yes | Yes (phase3) | OK |
| sqlite3 | Yes | Yes (phase3) | OK |
| i2c-tools | Yes | Yes (phase3) | OK |
| git | Yes | Yes (phase3) | OK |
| curl | Yes | Yes (phase3) | OK |
| batctl | Yes | Yes (phase3) | OK |
| wireless-tools | Yes (iwconfig, iwgetid) | Yes (phase3) | OK |
| wpasupplicant | Yes | Yes (phase3) | OK |
| dhcpcd5 | Yes | Yes (phase3) | OK |
| dnsmasq | Yes | Yes (phase5) | OK |
| iptables | Yes | Yes (phase3) | OK |
| **mpg123** | **Yes** | **No** | **MISSING** |
| **alsa-utils** | **Yes** | **No** | **MISSING** |
| **Pip Packages** | | | |
| smbus2 | Yes | Yes (phase3) | OK |
| rpi-ws281x | Yes | Yes (phase3) | OK |
| flask-socketio | Optional | Yes (phase3) | OK |
| flask-sqlalchemy | Optional | Yes (phase3) | OK |
| **requests** | **Yes** | **No** | **MISSING** |
| **psutil** | **Yes (tests)** | **No** | **MISSING (tests only)** |

---

## Configuration Issues

### 1. Systemd Service WorkingDirectory

**File:** `phase7_fieldtrainer.sh:473-474`

```bash
WorkingDirectory=/opt
ExecStart=/usr/bin/python3 /opt/field_trainer_main.py
```

**Issue:** The repository is cloned to `/opt` directly, so this is correct. However, verify that:
- The clone puts files in `/opt/` directly (not `/opt/FT_2025/`)
- The `data/` directory is created at `/opt/data/`

---

### 2. Database Path Consistency

**Multiple locations reference database:**
- `models_extended.py:25`: `/opt/data/field_trainer.db`
- `bridge_layer.py:292`: `/opt/data/field_trainer.db`

**Verify:** Phase 7 should create `/opt/data/` directory with correct permissions.

---

## Recommended Changes to phase3_packages.sh

Add these lines to the `UTIL_PACKAGES` array around line 486:

```bash
UTIL_PACKAGES=(
    "git"
    "curl"
    "mpg123"        # ADD - Required for MP3 audio playback
    "alsa-utils"    # ADD - Provides aplay, speaker-test for audio
)
```

Add pip packages after line 470:

```bash
# Install requests (for HTTP client functionality)
echo -n "  Checking requests... "
if python3 -c "import requests" 2>/dev/null; then
    print_success "already installed"
else
    print_info "installing via pip..."
    if sudo pip3 install requests --break-system-packages &>/dev/null; then
        print_success "installed"
    else
        print_warning "failed to install (tests may fail)"
    fi
fi
```

---

## Hardware/System Configuration (Already Handled)

These are correctly configured by your deployment scripts:

| Configuration | Phase | Status |
|--------------|-------|--------|
| SSH enabled | Phase 1 | OK |
| I2C enabled | Phase 1 | OK |
| SPI enabled | Phase 1 | OK |
| batman-adv module | Phase 4 | OK |
| WiFi interfaces | Phase 2 | OK |
| DNS/DHCP (dnsmasq) | Phase 5 | OK |
| NAT/Firewall | Phase 6 | OK |

---

## Test Commands After Deployment

Run these to verify all dependencies are working:

```bash
# Test audio dependencies
which mpg123 && echo "mpg123: OK" || echo "mpg123: MISSING"
which aplay && echo "aplay: OK" || echo "aplay: MISSING"
which speaker-test && echo "speaker-test: OK" || echo "speaker-test: MISSING"

# Test Python imports
python3 -c "import flask" && echo "Flask: OK"
python3 -c "import PIL" && echo "Pillow: OK"
python3 -c "import smbus2" && echo "smbus2: OK"
python3 -c "import rpi_ws281x" && echo "rpi-ws281x: OK"
python3 -c "import requests" && echo "requests: OK" || echo "requests: MISSING"

# Test network tools
which batctl && batctl -v
which iwconfig && echo "iwconfig: OK"

# Test Field Trainer main script
cd /opt && python3 -c "from field_trainer_main import *" && echo "Main imports: OK"
```

---

## Summary of Required Changes

### Immediate Fixes (Critical):

1. **Add to phase3_packages.sh APT packages:**
   - `mpg123`
   - `alsa-utils`

2. **Add to phase3_packages.sh pip packages:**
   - `requests`

### Optional Fixes (For Testing):

3. **Add to phase3_packages.sh pip packages:**
   - `psutil`
   - `pytest` (if you want to run tests on device)

---

## Files Modified

This analysis examined:
- `/home/user/deploy_scripts/install_menu.sh`
- `/home/user/deploy_scripts/phases/phase1_hardware.sh`
- `/home/user/deploy_scripts/phases/phase3_packages.sh`
- `/home/user/deploy_scripts/phases/phase7_fieldtrainer.sh`
- All Python files in `/home/user/FT_2025/`
- `/home/user/FT_2025/requirements.txt`
