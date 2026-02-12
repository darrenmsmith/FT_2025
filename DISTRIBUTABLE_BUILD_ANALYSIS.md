# Field Trainer Distributable Build Analysis

**Analysis Date:** 2025-12-30
**Purpose:** Identify mandatory vs. removable files for distributable installation package
**Target:** Clean repository suitable for cloning to new installations

---

## Summary Statistics

- **Total files in /opt:** 1,160
- **Git-tracked files:** 771
- **Untracked files:** ~389
- **Database backups:** 10 files in /opt/data/
- **Backup directories:** 9 timestamped backup sets
- **Documentation files (.md):** ~30

---

## 1. MANDATORY FILES (Core Operation)

### A. Python Application Core
**Location:** `/opt/`

#### Main Entry Points (CRITICAL)
- `field_trainer_main.py` - Main application entry point
- `field_trainer_core.py` - Core application logic
- `coach_interface.py` - Coach web interface (port 5001)
- `field_trainer_web.py` - Field trainer web interface
- `field_client_connection.py` - Client device connection handler

#### Hardware Control Modules
- `led_controller.py` - LED hardware control
- `led_hardware_test.py` - LED hardware testing
- `audio_manager.py` - Audio playback management
- `mpu65xx_touch_sensor.py` - Touch sensor interface
- `shutdown_leds.py` - Safe LED shutdown

#### Utility Modules
- `sync_all_clocks.py` - Network time synchronization

### B. Field Trainer Package
**Location:** `/opt/field_trainer/`

#### Core Modules (ALL REQUIRED)
```
field_trainer/
├── __init__.py                    ✅ Package init
├── db_manager.py                  ✅ Database operations
├── ft_audio.py                    ✅ Audio management
├── ft_config.py                   ✅ Configuration
├── ft_courses.py                  ✅ Course management
├── ft_heartbeat.py                ✅ Device heartbeat
├── ft_led.py                      ✅ LED control
├── ft_mesh.py                     ✅ Mesh networking
├── ft_models.py                   ✅ Data models
├── ft_monitor.py                  ✅ System monitoring
├── ft_registry.py                 ✅ Device registry
├── ft_touch.py                    ✅ Touch sensor
├── ft_touch_led_service.py        ✅ Touch+LED service
├── ft_version.py                  ✅ Version info
├── ft_webapp.py                   ✅ Web application
├── pattern_generator.py           ✅ Simon Says patterns
└── settings_manager.py            ✅ Settings management
```

#### Sub-packages
```
field_trainer/
├── athletic_platform/             ⚠️  Optional (future integration)
│   ├── __init__.py
│   ├── bridge_layer.py
│   ├── models_extended.py
│   └── test_integration.py
├── calibration/                   ✅ Touch calibration
│   ├── __init__.py
│   ├── calibration_logic.py
│   └── routes.py
├── routes/                        ✅ Web routes
│   ├── __init__.py
│   └── dashboard.py
└── scripts/                       ✅ Management scripts (see below)
```

### C. Services Layer
**Location:** `/opt/services/`

```
services/
├── __init__.py                    ✅ Package init
├── beep_test_service.py           ✅ Beep Test implementation
└── session_service.py             ✅ Session management
```

### D. Routes (API Endpoints)
**Location:** `/opt/routes/`

```
routes/
├── __init__.py                    ✅ Package init
├── beep_test_bp.py                ✅ Beep Test API
└── sessions_bp.py                 ✅ Sessions API
```

### E. Models
**Location:** `/opt/models/`

```
models/
├── __init__.py                    ✅ Package init
└── session_state.py               ✅ Session state management
```

### F. Management Scripts
**Location:** `/opt/scripts/`

```
scripts/
├── init_mac_filter.sh             ✅ MAC filtering setup
├── manage_mac_filter.sh           ✅ MAC filter management
├── ft-network-manager.py          ✅ Network management
├── create_beep_test_course.py     ✅ Beep Test course creation
├── vscode_setup.sh                ❌ Development only
└── github_deploy.sh               ❌ Development only
```

### G. Field Trainer Scripts
**Location:** `/opt/field_trainer/scripts/`

All scripts in this directory are **MANDATORY** for field operations:
```
field_trainer/scripts/
├── backup_audio_files.sh          ✅ Audio backup
├── calibrate_touch.sh             ✅ Touch calibration
├── check_mesh_status.sh           ✅ Mesh monitoring
├── check_touch_hardware.sh        ✅ Hardware diagnostics
├── check_touch_led_status.sh      ✅ Service status
├── check_touch_status.sh          ✅ Touch diagnostics
├── deploy_audio_devices.sh        ✅ Audio deployment
├── deploy_code_update.sh          ✅ Code deployment
├── reboot_all_devices.sh          ✅ Device management
├── start_all_touch_led.sh         ✅ Service control
├── stop_all_touch_led.sh          ✅ Service control
├── test_all_audio.sh              ✅ Audio testing
├── test_touch_led.sh              ✅ LED testing
├── test_touch.sh                  ✅ Touch testing
├── touch_led_control.sh           ✅ Service control
├── tune_touch_interactive.sh      ✅ Interactive tuning
└── tune_touch.sh                  ✅ Touch tuning
```

### H. Templates (Web UI)
**Location:** `/opt/field_trainer/templates/`

#### Base Templates (REQUIRED)
- `base.html` - Base template with navigation

#### Beep Test Templates
- `beep_test_setup.html` - Setup page
- `beep_test_monitor.html` - Monitor page
- `beep_test_results.html` - Results page

#### Session Templates
- `session_setup_cones.html` - Cone/Simon Says setup
- `session_history.html` - Session history
- `session_monitor.html` - Session monitoring (old style)

#### Dashboard
- `dashboard/index.html` - Main dashboard

#### Additional (Check if still used)
- `health.html` - Health check page
- `index.html` - Landing page

### I. Static Assets
**Location:** `/opt/static/` and `/opt/field_trainer/static/`

#### Top-level Static Files
```
static/
├── default-avatar.png             ✅ Default avatar
├── FT_icon.svg                    ✅ Field Trainer icon
├── athlete_import_template.csv    ✅ Import template
├── css/
│   └── style.css                  ✅ Main stylesheet
└── js/
    └── app.js                     ✅ Main JavaScript
```

#### Field Trainer Static (Vendor Libraries)
```
field_trainer/static/vendor/
├── bootstrap/                     ✅ Bootstrap CSS/JS framework
├── bootstrap-icons/               ✅ Icon library
└── sortable/                      ✅ Sortable.js (drag-drop)
```

### J. Audio Files
**Location:** `/opt/field_trainer/audio/`

```
audio/
├── all_good.mp3                   ✅ Success sound
├── default_beep.mp3               ✅ Default beep
├── field_trainer_ready.mp3        ✅ Ready sound
├── female/                        ✅ Female voice prompts (entire directory)
└── male/                          ✅ Male voice prompts (entire directory)
```

### K. Data Directory
**Location:** `/opt/data/`

#### For Distribution (Empty Database + Config Templates)
- `field_trainer.db` - **SPECIAL:** Empty schema with built-in courses + AI Team
- `network-config.json` - Network configuration template (empty/defaults)
- `network-status.json` - Network status template (empty/defaults)

### L. Configuration Files
**Location:** `/opt/`

- `requirements.txt` ✅ Python dependencies
- `.gitignore` ✅ Git ignore rules
- `README.md` ✅ Basic readme (can be updated for distribution)

### M. Deployment Scripts (Top-level)
**Location:** `/opt/`

```
✅ deploy_all_clients.sh          - Deploy to all client devices
✅ deploy_clients_simple.sh       - Simple deployment
✅ restart_all_clients.sh         - Restart all clients
✅ setup_client_services.sh       - Client service setup
✅ unified_provisioner_v2.sh      - Unified provisioning
✅ update_client_services.sh      - Update client services
❌ deploy_test_mode_fix.sh        - Development fix
```

---

## 2. REMOVABLE FILES (Not Needed for Distribution)

### A. Documentation Files (.md) - ALL REMOVABLE
**Location:** `/opt/`

```
❌ ADVANCED_UI_INTEGRATION_SUMMARY.md
❌ ATHLETES_IMPLEMENTATION_COMPLETE.md
❌ BUG_FIX_D0_PREMATURE_BEEP.md
❌ COACH_FRIENDLY_UI_UPDATE.md
❌ CONTINUE_TO_N_DEBUG.md
❌ CONTINUE_TO_N_IMPLEMENTATION.md
❌ CRITICAL_BUG_FIX_SESSION_ENDING.md
❌ DEBOUNCE_INCREASE_TO_1000MS.md
❌ DEBOUNCE_LOGIC.md
❌ EXAMPLE_COURSES_GUIDE.md
❌ IMPLEMENTATION_COMPLETE.md
❌ PHASE_1_IMPLEMENTATION_SUMMARY.md
❌ PHASE1_UI_FIXES_COMPLETE.md
❌ PHASE1_UI_FIXES_SIMON_SAYS.md
❌ PHASE_2_IMPLEMENTATION_SUMMARY.md
❌ PHASE_3_IMPLEMENTATION_SUMMARY.md
❌ SEQUENTIAL_MODE_MULTI_ATHLETE_FIX.md
❌ SETTINGS_TODO.md
❌ SIMON_SAYS_DEVELOPMENT_PLAN.md
❌ SIMON_SAYS_IMPLEMENTATION_COMPLETE.md
❌ SIMON_SAYS_IMPLEMENTATION_SUMMARY.md
❌ simon_says_operation.md
❌ TEAM_MANAGEMENT_IMPLEMENTATION_SUMMARY.md
❌ TEAM_MIGRATION_FINAL_SUMMARY.md
❌ TEST_PROGRAMS_REGISTRY.md

✅ FIELD_TRAINER_TECHNICAL_OVERVIEW.md  - KEEP (important reference)
```

### B. Backup Directories - ALL REMOVABLE
**Location:** `/opt/backups/` and `/opt/backup/`

```
❌ backups/simon_says_timing_fix_20251208_181849/
❌ backups/calibration_20251112_091424/
❌ backups/phase1_backup_20251012_071802/
❌ backups/phase1_complete_20251017_112825/
❌ backups/phase2_complete_20251017_151953/
❌ backups/phase2_complete_20251017_152013/
❌ backups/phase2_start_20251025_124104/
❌ backups/phase3_before_attribution_fix_20251018_103308/
❌ backups/phase3_complete_20251018_162255/
❌ backup/  (entire directory)
```

### C. Database Backups - ALL REMOVABLE
**Location:** `/opt/data/`

```
❌ field_trainer.db.backup_20251106_075339
❌ field_trainer.db.backup_20251106_081955
❌ field_trainer.db.backup_20251106_082353
❌ field_trainer.db.backup_20251120_164313
❌ field_trainer.db.backup_advanced_20251121_115600
❌ field_trainer.db.backup_athletes_20251106_081858
❌ field_trainer.db.backup_before_advanced_20251130_154420
❌ field_trainer.db.backup_before_restore
❌ field_trainer.db.before_constraint
```

### D. Test Scripts - KEEP FOR DEBUGGING
**Location:** `/opt/`

```
⚠️  12_test_backwards_compatibility.py   - KEEP (useful for testing)
⚠️  test_api_integration.py              - KEEP
⚠️  test_attribution_logic.py            - KEEP
⚠️  test_beep_direct.py                  - KEEP
⚠️  test_beep_pattern.py                 - KEEP
⚠️  test_concurrency.py                  - KEEP
⚠️  test_database_integrity.py           - KEEP
⚠️  test_load_stress.py                  - KEEP
⚠️  test_team_management.py              - KEEP
⚠️  test_touch_sequences.py              - KEEP
⚠️  run_tests.sh                         - KEEP
```

### E. Migration/Utility Scripts - REMOVABLE (one-time use)
**Location:** `/opt/`

```
❌ migrate_athletes_simple.py
❌ migrate_athletes_upgrade.py
❌ migrate_teams_enhancement.py
❌ update_course_descriptions.py
❌ create_example_advanced_courses.py
❌ create_all_management_scripts.sh
```

### F. Deprecated/Old Files - REMOVABLE
**Location:** `/opt/`

```
❌ coach_interface_fixed.py           - Old version
❌ coach_interface_refactored.py      - Old version
❌ field_client_connection_updated.py - Updated version (check if needed)
❌ athlete_helpers.py                 - Check if still used
❌ athlete_routes.py                  - Check if still used
❌ start_field_trainer.sh             - Systemd service used instead
❌ templates/coach/*                  - Old coach templates (duplicates)
```

### G. IDE/Development Files - REMOVABLE
**Location:** `/opt/`

```
❌ .vscode/              - VS Code settings
❌ .claude/              - Claude AI cache
❌ static/js/app.js.backup  - Backup file
❌ coach_interface.py.backup - Backup file
```

### H. Git Repository - DECISION NEEDED
**Location:** `/opt/.git/`

```
⚠️  .git/  - DECISION:
   - KEEP if distributing as git repository (recommended)
   - REMOVE if distributing as archive package
```

### I. Python Cache - AUTO-GENERATED (Remove)
**Location:** Multiple `__pycache__/` directories

```
❌ All __pycache__/ directories (auto-generated)
❌ All *.pyc files (auto-generated)
```

---

## 3. DATABASE INITIALIZATION REQUIREMENTS

### Empty Database with Required Data

The distributable should include a clean `field_trainer.db` with:

#### A. Schema (All Tables)
- athletes
- athlete_notes
- beep_test_results
- beep_test_sessions
- calibration_data
- coach_profiles
- cone_layouts
- courses
- device_registry
- failed_touches
- network_events
- runs
- sessions
- simon_says_patterns
- simon_says_segments
- teams

#### B. Built-in Courses (marked with built_in = 1)
Query to identify:
```sql
SELECT course_id, name, category FROM courses WHERE built_in = 1;
```

Expected built-in courses:
- Standard drills (40yd sprint, Pro Agility, etc.)
- Beep Test courses (15m, 20m)
- Example Simon Says courses

#### C. AI Team (team_id with special marker)
Query to identify:
```sql
SELECT team_id, name FROM teams WHERE name = 'AI Team' OR team_id = '<specific_id>';
```

#### D. Exclude User Data
- Remove all athlete records
- Remove all session/run records
- Remove all user-created teams
- Remove all user-created courses
- Keep only system defaults

### Database Creation Script Needed
**Recommendation:** Create `/opt/scripts/init_database.py`
- Creates empty schema
- Inserts built-in courses
- Inserts AI Team
- Sets up indexes and constraints

---

## 4. RECOMMENDED DISTRIBUTION STRUCTURE

### Option A: Git Repository (Recommended)

```
field-trainer/                     # Git repository root
├── .git/                          ✅ Full git history
├── .gitignore                     ✅ Ignore rules
├── README.md                      ✅ Installation guide
├── requirements.txt               ✅ Python deps
├── FIELD_TRAINER_TECHNICAL_OVERVIEW.md  ✅ Technical docs
│
├── field_trainer/                 ✅ Main package
│   ├── __init__.py
│   ├── *.py (all core modules)
│   ├── audio/                     ✅ Audio files
│   ├── calibration/               ✅ Calibration package
│   ├── routes/                    ✅ Web routes
│   ├── scripts/                   ✅ Management scripts
│   ├── static/                    ✅ Vendor libraries
│   └── templates/                 ✅ HTML templates
│
├── services/                      ✅ Service layer
├── routes/                        ✅ API routes
├── models/                        ✅ Data models
├── scripts/                       ✅ Top-level scripts
├── static/                        ✅ Static assets
├── templates/                     ✅ Templates (if needed)
│
├── data/                          ✅ Data directory
│   ├── field_trainer.db           ✅ Empty DB (built-in courses + AI Team)
│   ├── network-config.json        ✅ Template
│   └── network-status.json        ✅ Template
│
├── *.py (entry points)            ✅ Main Python files
├── *.sh (deployment scripts)      ✅ Deployment scripts
└── tests/                         ⚠️  Optional test scripts
```

### Option B: Archive Package (Alternative)

Same structure as Option A, but distributed as:
- `field-trainer-v1.0.0.tar.gz`
- `field-trainer-v1.0.0.zip`

No `.git/` directory included.

---

## 5. INSTALLATION SCRIPT REQUIREMENTS

The build guide mentions Phase 6 clones to `/opt/`. The installation should:

### A. Prerequisites Check
- Python 3.7+
- pip installed
- Git installed (if cloning)
- Required system packages (batctl, dnsmasq, etc.)

### B. Installation Steps
1. Clone repository to `/opt/`
   ```bash
   cd /opt
   git clone <repo-url> .
   git checkout <branch>  # e.g., main
   ```

2. Install Python dependencies
   ```bash
   pip3 install -r requirements.txt
   ```

3. Initialize database (if not included)
   ```bash
   python3 scripts/init_database.py
   ```

4. Set permissions
   ```bash
   chmod +x scripts/*.sh
   chmod +x field_trainer/scripts/*.sh
   chmod +x *.sh
   ```

5. Create systemd service
   ```bash
   sudo cp field-trainer.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable field-trainer.service
   ```

### C. Post-Installation
- Configure network settings
- Run hardware tests
- Deploy to client devices

---

## 6. FILES TO REVIEW (Uncertain Status)

These files need manual review to determine if they're needed:

```
⚠️  athlete_helpers.py            - Is this still imported anywhere?
⚠️  athlete_routes.py             - Is this still imported anywhere?
⚠️  field_client_connection_updated.py  - Which version is current?
⚠️  field_trainer/athletic_platform/  - Future feature or active?
⚠️  templates/coach/              - Duplicate templates?
⚠️  scripts/vscode_setup.sh       - Dev only or needed?
⚠️  scripts/github_deploy.sh      - Dev only or needed?
```

---

## 7. RECOMMENDED CLEANUP STEPS

### Step 1: Remove Documentation
```bash
cd /opt
rm -f *_SUMMARY.md *_COMPLETE.md *_PLAN.md *_DEBUG.md *_IMPLEMENTATION.md
rm -f BUG_FIX_*.md DEBOUNCE_*.md SETTINGS_TODO.md simon_says_operation.md
# Keep FIELD_TRAINER_TECHNICAL_OVERVIEW.md and README.md
```

### Step 2: Remove Backups
```bash
rm -rf /opt/backups/
rm -rf /opt/backup/
rm -f /opt/data/field_trainer.db.backup*
rm -f /opt/data/field_trainer.db.before*
```

### Step 3: Remove Old/Duplicate Files
```bash
rm -f coach_interface_fixed.py
rm -f coach_interface_refactored.py
rm -f static/js/app.js.backup
rm -f coach_interface.py.backup
```

### Step 4: Remove Migration Scripts
```bash
rm -f migrate_*.py
rm -f update_course_descriptions.py
rm -f create_example_advanced_courses.py
rm -f create_all_management_scripts.sh
```

### Step 5: Remove IDE Files
```bash
rm -rf .vscode/
rm -rf .claude/
```

### Step 6: Clean Python Cache
```bash
find /opt -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /opt -type f -name "*.pyc" -delete
find /opt -type f -name "*.pyo" -delete
```

### Step 7: Review Uncertain Files
```bash
# Manual review needed - check imports and usage
ls -la athlete_helpers.py
ls -la athlete_routes.py
ls -la field_client_connection_updated.py
ls -laR field_trainer/athletic_platform/
```

### Step 8: Create Clean Database
```bash
# Create script to initialize database with:
# - Empty schema
# - Built-in courses only
# - AI Team only
# - No user data
python3 scripts/init_database.py > /opt/data/field_trainer.db
```

---

## 8. FINAL DISTRIBUTABLE CHECKLIST

### Essential Components ✅
- [ ] All Python core modules present
- [ ] All HTML templates present
- [ ] All static assets (CSS, JS, icons) present
- [ ] Vendor libraries (Bootstrap, Bootstrap Icons, Sortable.js)
- [ ] All audio files (male/female voices, sounds)
- [ ] Management scripts (deployment, diagnostics, control)
- [ ] Empty database with built-in courses and AI Team
- [ ] Network config templates
- [ ] requirements.txt with all dependencies
- [ ] README.md with installation instructions
- [ ] .gitignore properly configured

### Documentation ✅
- [ ] README.md - Installation guide
- [ ] FIELD_TRAINER_TECHNICAL_OVERVIEW.md - Technical reference
- [ ] Remove all other .md files (implementation notes, bug fixes, etc.)

### Cleanup ✅
- [ ] No backup directories
- [ ] No database backups
- [ ] No Python cache files
- [ ] No IDE configuration
- [ ] No migration scripts
- [ ] No old/deprecated files

### Testing ✅
- [ ] Fresh clone to /opt/ works
- [ ] pip install -r requirements.txt works
- [ ] Database initializes correctly
- [ ] Services start successfully
- [ ] Web interfaces accessible
- [ ] Hardware control functional
- [ ] Client deployment works

---

## 9. ESTIMATED SIZE REDUCTION

### Current Size
- Total: 1,160 files

### After Cleanup
- Remove: ~400 files
  - Backups: ~350 files
  - Documentation: ~30 files
  - Old/duplicate: ~10 files
  - Python cache: ~10 files

- **Remaining: ~760 files**
- **Size reduction: ~35%**

### Database
- Current: 1,265,664 bytes (1.2 MB)
- Clean: ~200,000 bytes (200 KB) estimated
- **Size reduction: ~85%**

---

## 10. NEXT STEPS

1. ✅ Review uncertain files (athlete_helpers, athlete_routes, etc.)
2. ✅ Create database initialization script
3. ✅ Test cleanup on development system
4. ✅ Create distributable repository/archive
5. ✅ Test fresh installation on clean Raspberry Pi
6. ✅ Document installation process
7. ✅ Create new GitHub repository
8. ✅ Push cleaned codebase

---

## APPENDIX: Commands for Verification

### A. Find Large Files
```bash
find /opt -type f -size +1M -exec ls -lh {} \;
```

### B. Count Files by Type
```bash
find /opt -type f -name "*.py" | wc -l
find /opt -type f -name "*.html" | wc -l
find /opt -type f -name "*.md" | wc -l
find /opt -type f -name "*.sh" | wc -l
```

### C. Check for Unused Python Files
```bash
# Find Python files not imported
for f in /opt/*.py; do
  basename=$(basename "$f" .py)
  if ! grep -r "import $basename" /opt --include="*.py" | grep -v "$f"; then
    echo "Potentially unused: $f"
  fi
done
```

### D. Verify All Imports Resolve
```bash
python3 -c "import sys; sys.path.insert(0, '/opt'); import field_trainer_main"
```

---

**END OF ANALYSIS**
