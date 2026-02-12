# Build Scripts Review - USB Build System
**Location:** `/mnt/usb/ft_usb_build/`
**Date:** 2025-12-30
**Purpose:** Review build scripts for distributable repository compatibility

---

## OVERVIEW

The USB build system at `/mnt/usb/ft_usb_build/` contains installation scripts for setting up Device 0 (Gateway). The scripts follow a phased approach with the following structure:

### Main Build Script
- **File:** `ft_build.sh`
- **Purpose:** Interactive menu-driven installer
- **Status:** ✅ Good structure, well-organized

### Phase Scripts (Actual Files vs. Guide Naming)

| Guide | Actual File | Description |
|-------|-------------|-------------|
| Phase 0 | `phase1_hardware.sh` | Hardware verification |
| Phase 1 | `phase3_packages.sh` | Package installation |
| Phase 2 | `phase2_internet.sh` | Internet connection (wlan1) |
| Phase 3 | `phase4_mesh.sh` | BATMAN mesh network |
| Phase 4 | `phase5_dns.sh` | DNS/DHCP (dnsmasq) |
| Phase 5 | `phase6_nat.sh` | NAT/Firewall (iptables) |
| Phase 6 | `phase7_fieldtrainer.sh` | Field Trainer application |

**Note:** Phase numbering mismatch between guide documentation and actual scripts!

---

## CRITICAL FINDINGS

### 🔴 ISSUE #1: Missing Database Initialization

**Problem:**
- `phase7_fieldtrainer.sh` (Phase 6) clones the repository
- Creates `/opt/data/` directory
- **BUT DOES NOT initialize the database!**
- No call to `init_clean_database.py` or any database setup

**Current Behavior:**
```bash
# Step 5: Creating Data Directory (line 347-365)
DATA_DIR="$APP_DIR/data"
if [ -d "$DATA_DIR" ]; then
    print_info "Data directory already exists"
else
    print_info "Creating $DATA_DIR..."
    mkdir -p $DATA_DIR
fi
# ... that's it. No database creation!
```

**Impact:**
- Fresh installations will have an empty `/opt/data/` directory
- Field Trainer application will fail on first startup (no database)
- Manual database initialization required after installation

**Required Fix:**
Add database initialization step after Step 5 in `phase7_fieldtrainer.sh`:

```bash
################################################################################
# Step 5.5: Initialize Clean Database
################################################################################

echo "Step 5.5: Initializing Database..."
echo "-----------------------------------"

DB_FILE="$DATA_DIR/field_trainer.db"
INIT_SCRIPT="$APP_DIR/scripts/init_clean_database.py"

if [ -f "$DB_FILE" ]; then
    print_warning "Database already exists at $DB_FILE"

    # Show database info
    DB_SIZE=$(stat -c%s "$DB_FILE" 2>/dev/null || echo "0")
    print_info "Current size: $DB_SIZE bytes"

    read -p "Reinitialize database? This will ERASE all data! (y/n): " REINIT

    if [[ "$REINIT" =~ ^[Yy]$ ]]; then
        print_warning "Creating backup..."
        BACKUP_FILE="$DB_FILE.backup_$(date +%Y%m%d_%H%M%S)"
        cp "$DB_FILE" "$BACKUP_FILE"
        print_success "Backup saved to $BACKUP_FILE"

        INIT_DB=true
    else
        print_info "Keeping existing database"
        INIT_DB=false
    fi
else
    print_info "No database found - will create clean database"
    INIT_DB=true
fi

if [ "$INIT_DB" = true ]; then
    if [ -f "$INIT_SCRIPT" ]; then
        print_info "Running database initialization script..."

        if python3 "$INIT_SCRIPT" "$DB_FILE"; then
            print_success "Database initialized successfully"

            # Verify database
            if [ -f "$DB_FILE" ]; then
                DB_SIZE=$(stat -c%s "$DB_FILE" 2>/dev/null)
                print_info "Database created: $DB_SIZE bytes"

                # Quick verification
                COURSE_COUNT=$(python3 -c "import sqlite3; conn = sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM courses WHERE is_builtin=1').fetchone()[0]); conn.close()")
                TEAM_COUNT=$(python3 -c "import sqlite3; conn = sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM teams').fetchone()[0]); conn.close()")

                print_success "Built-in courses: $COURSE_COUNT"
                print_success "Teams: $TEAM_COUNT (AI Team)"
            else
                print_error "Database file not created!"
                ERRORS=$((ERRORS + 1))
            fi
        else
            print_error "Database initialization failed!"
            ERRORS=$((ERRORS + 1))
        fi
    else
        print_error "Initialization script not found: $INIT_SCRIPT"
        print_warning "You will need to manually initialize the database"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""
```

---

### 🔴 ISSUE #2: Repository URL Hardcoded

**Problem:**
```bash
REPO_URL="https://github.com/darrenmsmith/FT_2025.git"
DEFAULT_BRANCH="main"
```

**Current Repository:** `FT_2025` (development repository)
**Distributable Repository:** TBD (needs to be created)

**Impact:**
- Build script points to current development repository
- Needs to be updated when distributable repository is created

**Required Fix:**
Update `phase7_fieldtrainer.sh` line 25-26:
```bash
REPO_URL="https://github.com/[NEW_ORG]/field-trainer.git"  # Update when new repo created
DEFAULT_BRANCH="main"
```

---

### 🟡 ISSUE #3: Package Installation Order

**Current Order (from build guide):**
1. Phase 0: Hardware verification
2. **Phase 2: Internet connection** (gives internet access)
3. **Phase 1: Package installation** (needs internet)
4. Phases 3-6: Configuration

**Issue:**
- Build guide says Phase 2 should run before Phase 1
- But actual scripts are numbered differently:
  - `phase2_internet.sh` = Phase 2 in guide
  - `phase3_packages.sh` = Phase 1 in guide

**Impact:**
- Confusion between documentation and actual script files
- Not a functional problem if scripts are run in order via menu

**Recommendation:**
Renumber scripts to match guide documentation:
- `phase0_hardware.sh` (currently phase1_hardware.sh)
- `phase1_packages.sh` (currently phase3_packages.sh)
- `phase2_internet.sh` (correct)
- `phase3_mesh.sh` (currently phase4_mesh.sh)
- etc.

---

### 🟢 GOOD: Clone Process

**Current Implementation (line 306-308):**
```bash
cd $APP_DIR
if sudo -u pi git clone --branch "$BRANCH_NAME" "$REPO_URL" .; then
    print_success "Repository cloned successfully"
```

**Status:** ✅ Correct
- Clones directly into `/opt` (not `/opt/field_trainer/`)
- Uses `--branch` to specify branch
- Uses `.` to clone into current directory
- Runs as `pi` user

This matches our distributable requirements perfectly!

---

### 🟢 GOOD: Service File

**Current Implementation (line 464-485):**
```ini
[Unit]
Description=Field Trainer Application - Device 0
After=network.target batman-mesh.service dnsmasq.service
Wants=batman-mesh.service dnsmasq.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt
ExecStart=/usr/bin/python3 /opt/field_trainer_main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

**Status:** ✅ Correct
- Correct working directory: `/opt`
- Correct entry point: `/opt/field_trainer_main.py`
- Dependencies on mesh and dnsmasq services
- Auto-restart enabled

---

### 🟢 GOOD: Dependency Installation

**Current Implementation:**
1. Checks for requirements.txt
2. Prompts user to install
3. Uses `pip3 install -r requirements.txt --break-system-packages`

**Status:** ✅ Good
- Handles requirements.txt if present
- Uses `--break-system-packages` for Debian 13 compatibility

---

### 🟢 GOOD: PIL/Pillow Handling

**Current Implementation (line 92-132):**
- Checks if PIL is installed
- Auto-installs if missing
- Tries apt first (`python3-pil`)
- Falls back to pip if needed
- Verifies installation after

**Status:** ✅ Excellent
- Critical for coach interface (port 5001)
- Handles multiple installation methods
- Verifies before continuing

---

## COMPARISON WITH DISTRIBUTABLE REQUIREMENTS

### Required Files for Distributable

| Requirement | In Repository? | In Build Script? | Status |
|-------------|----------------|------------------|--------|
| Core Python modules | ✅ Yes | N/A | ✅ |
| field_trainer package | ✅ Yes | N/A | ✅ |
| Templates | ✅ Yes | N/A | ✅ |
| Static assets | ✅ Yes | N/A | ✅ |
| Audio files | ✅ Yes | N/A | ✅ |
| Scripts | ✅ Yes | N/A | ✅ |
| requirements.txt | ✅ Yes | ✅ Installed | ✅ |
| **init_clean_database.py** | ✅ Created | ❌ **NOT CALLED** | 🔴 **CRITICAL** |
| Clean database | ❌ No | ❌ **NOT CREATED** | 🔴 **CRITICAL** |

---

## RECOMMENDED CHANGES

### Priority 1: CRITICAL (Must Fix Before Distribution)

#### 1. Add Database Initialization to phase7_fieldtrainer.sh

**Location:** After Step 5 (line ~370)
**Action:** Add new Step 5.5 as shown in Issue #1 above

**Steps:**
1. Check if database exists
2. If not, run `python3 /opt/scripts/init_clean_database.py /opt/data/field_trainer.db`
3. Verify database created correctly
4. Verify built-in courses and AI Team present

#### 2. Update Repository URL

**Location:** `phase7_fieldtrainer.sh` line 25
**Action:** Update when new distributable repository is created

**Current:**
```bash
REPO_URL="https://github.com/darrenmsmith/FT_2025.git"
```

**Future:**
```bash
REPO_URL="https://github.com/[ORGANIZATION]/field-trainer.git"  # Update after repo created
```

---

### Priority 2: RECOMMENDED (Should Fix)

#### 3. Renumber Phase Scripts for Clarity

**Current:**
- phase1_hardware.sh
- phase2_internet.sh
- phase3_packages.sh
- phase4_mesh.sh
- phase5_dns.sh
- phase6_nat.sh
- phase7_fieldtrainer.sh

**Recommended:**
- phase0_hardware.sh (matches guide)
- phase1_internet.sh (matches guide - internet BEFORE packages)
- phase2_packages.sh (matches guide)
- phase3_mesh.sh (matches guide)
- phase4_dns.sh (matches guide)
- phase5_nat.sh (matches guide)
- phase6_fieldtrainer.sh (matches guide)

**Why:**
- Documentation consistency
- Less confusion for users
- Matches recommended installation order

---

### Priority 3: NICE TO HAVE (Optional)

#### 4. Add Database Verification to Service Startup

Add check in phase7_fieldtrainer.sh before starting service:

```bash
# Before starting service, verify database exists
if [ ! -f "$DATA_DIR/field_trainer.db" ]; then
    print_error "Database not found! Service will fail to start."
    print_info "Run: python3 /opt/scripts/init_clean_database.py /opt/data/field_trainer.db"
    ERRORS=$((ERRORS + 1))
fi
```

#### 5. Add Post-Installation Verification

After service starts, verify:
- Database is accessible
- Web interfaces respond (ports 5000, 5001)
- Built-in courses are available

---

## DISTRIBUTABLE REPOSITORY CHECKLIST

When creating the new distributable repository, ensure:

### ✅ Repository Contents
- [ ] All core Python modules
- [ ] field_trainer package with all subpackages
- [ ] Templates (HTML files)
- [ ] Static assets (CSS, JS, images, vendor libraries)
- [ ] Audio files (male/female voices)
- [ ] Management scripts
- [ ] `requirements.txt`
- [ ] `README.md` with installation instructions
- [ ] `FIELD_TRAINER_TECHNICAL_OVERVIEW.md`
- [ ] **`/opt/scripts/init_clean_database.py`** ✅ Created
- [ ] `.gitignore`

### ❌ DO NOT Include
- [ ] Backup directories
- [ ] Database backups
- [ ] Development documentation (.md files except README and Technical Overview)
- [ ] Migration scripts
- [ ] Old/duplicate files
- [ ] .vscode, .claude
- [ ] Python cache (__pycache__)
- [ ] User data in database

### ✅ Database Requirements
- [ ] Clean database NOT included in repository (created during installation)
- [ ] `init_clean_database.py` script present
- [ ] Script creates 14 built-in courses
- [ ] Script creates AI Team
- [ ] Script creates all 17 tables
- [ ] No user data

---

## INSTALLATION FLOW VERIFICATION

### Current Build Flow (After Fixes)

1. **Phase 0: Hardware Verification**
   - Check Trixie OS
   - Check interfaces (wlan0, wlan1)
   - Check kernel modules

2. **Phase 2: Internet Connection** ⚠️ Note: Phase 2 runs BEFORE Phase 1
   - Configure wlan1
   - Connect to WiFi
   - Get internet access

3. **Phase 1: Package Installation** (needs internet from Phase 2)
   - Install batctl, dnsmasq, iptables
   - Install Python packages (Flask, PIL, etc.)

4. **Phase 3: BATMAN Mesh**
   - Configure wlan0 for mesh
   - Create bat0 interface
   - Assign IP 192.168.99.100

5. **Phase 4: DNS/DHCP**
   - Configure dnsmasq
   - DHCP range: 192.168.99.101-200

6. **Phase 5: NAT/Firewall**
   - Enable IP forwarding
   - Configure iptables
   - Internet sharing

7. **Phase 6: Field Trainer**
   - Clone repository to /opt
   - **Initialize clean database** ← ADD THIS
   - Install Python dependencies
   - Create systemd service
   - Start service

### Expected Result After Installation

```
/opt/
├── field_trainer_main.py           ✅ Entry point
├── field_trainer/                  ✅ Main package
├── services/                       ✅ Service layer
├── routes/                         ✅ API routes
├── models/                         ✅ Data models
├── scripts/
│   └── init_clean_database.py      ✅ Database init script
├── static/                         ✅ Assets
├── templates/                      ✅ HTML templates
├── data/
│   └── field_trainer.db            ✅ Clean database (204 KB)
│                                      - 14 built-in courses
│                                      - AI Team
│                                      - No user data
├── requirements.txt                ✅ Dependencies
└── README.md                       ✅ Instructions
```

---

## TESTING CHECKLIST

Before finalizing build scripts:

### Test on Fresh Raspberry Pi
- [ ] Raspberry Pi OS Trixie (Debian 13) clean install
- [ ] Run Phase 0 (hardware verification)
- [ ] Run Phase 2 (internet connection)
- [ ] Verify internet access works
- [ ] Run Phase 1 (package installation)
- [ ] Run Phases 3-5 (mesh, DNS, NAT)
- [ ] Run Phase 6 (Field Trainer application)
- [ ] **Verify database created correctly**
- [ ] Verify 14 built-in courses present
- [ ] Verify AI Team present
- [ ] Verify service starts successfully
- [ ] Access web interface on port 5000
- [ ] Access coach interface on port 5001
- [ ] Test Beep Test functionality
- [ ] Test Simon Says functionality

### Verify Database Contents
```bash
# After installation, verify database
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/opt/data/field_trainer.db')
cursor = conn.cursor()

# Count built-in courses
cursor.execute("SELECT COUNT(*) FROM courses WHERE is_builtin = 1")
print(f"Built-in courses: {cursor.fetchone()[0]} (expect 14)")

# Count teams
cursor.execute("SELECT COUNT(*) FROM teams")
print(f"Teams: {cursor.fetchone()[0]} (expect 1)")

# Count user data
cursor.execute("SELECT COUNT(*) FROM athletes")
print(f"Athletes: {cursor.fetchone()[0]} (expect 0)")

cursor.execute("SELECT COUNT(*) FROM sessions")
print(f"Sessions: {cursor.fetchone()[0]} (expect 0)")

conn.close()
EOF
```

Expected output:
```
Built-in courses: 14 (expect 14) ✅
Teams: 1 (expect 1) ✅
Athletes: 0 (expect 0) ✅
Sessions: 0 (expect 0) ✅
```

---

## ACTION ITEMS

### Immediate (Before Creating Distributable Repo)

1. **Update phase7_fieldtrainer.sh**
   - Add database initialization (Step 5.5)
   - Test on development system
   - Verify database created correctly

2. **Create distributable repository**
   - Execute cleanup (remove ~400 files)
   - Consolidate file_client_connection versions
   - Verify init_clean_database.py is present
   - Push to new repository

3. **Update build script repository URL**
   - Change REPO_URL in phase7_fieldtrainer.sh
   - Test fresh clone

### After Distributable Repo Created

4. **Update USB build scripts**
   - Copy updated phase7_fieldtrainer.sh to USB
   - Update REPO_URL
   - Test full installation on clean Pi

5. **Documentation**
   - Update build guide with database initialization step
   - Document expected database contents
   - Add verification commands

---

## FILES TO UPDATE ON USB

### Primary File: phase7_fieldtrainer.sh
**Location:** `/mnt/usb/ft_usb_build/phases/phase7_fieldtrainer.sh`

**Changes needed:**
1. Line 25: Update REPO_URL (after new repo created)
2. After line ~370: Add Step 5.5 (database initialization)
3. Verification: Check database before starting service

### Secondary File: Build Guide
**Location:** `/home/pi/build/FIELD_TRAINER_BUILD_GUIDE.md`

**Changes needed:**
1. Add database initialization to Phase 6 description
2. Add database verification commands
3. Update repository URL (after creation)

---

## CONCLUSION

The USB build system is **95% ready** for distributable use. The only critical missing piece is **database initialization** in phase7_fieldtrainer.sh.

### Summary of Issues:
- 🔴 **CRITICAL:** Database initialization not implemented
- 🔴 **CRITICAL:** Repository URL needs updating (when new repo created)
- 🟡 **RECOMMENDED:** Phase script numbering mismatch
- 🟢 **GOOD:** Clone process, service file, dependency handling all correct

### Required Actions:
1. Add Step 5.5 to phase7_fieldtrainer.sh (database initialization)
2. Test database initialization on development system
3. Update REPO_URL after creating distributable repository
4. Update USB build scripts
5. Test full installation on fresh Raspberry Pi

**Estimated time to fix:** 30-60 minutes
**Risk level:** LOW (well-defined changes)
**Priority:** HIGH (blocks distribution)

---

**Next Steps:**
1. Review this analysis
2. Approve database initialization approach
3. Update phase7_fieldtrainer.sh
4. Test on development system
5. Proceed with distributable repository creation
