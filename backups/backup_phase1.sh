#!/bin/bash
# Field Trainer Phase 1 Backup Script
# Run this BEFORE making any changes
# Device: Device 0 (192.168.99.100)

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Field Trainer Phase 1 - Backup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create backup directory with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/phase1_backup_${TIMESTAMP}"

echo -e "${YELLOW}Creating backup directory: ${BACKUP_DIR}${NC}"
sudo mkdir -p "${BACKUP_DIR}"
sudo chown pi:pi "${BACKUP_DIR}"

# Function to backup a file
backup_file() {
    local file=$1
    local description=$2
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Backing up: $description"
        sudo cp -p "$file" "${BACKUP_DIR}/" 2>/dev/null || {
            echo -e "${RED}✗${NC} Failed to backup: $file"
            return 1
        }
    else
        echo -e "${YELLOW}⚠${NC} File not found (skipping): $file"
    fi
}

# Function to backup a directory
backup_directory() {
    local dir=$1
    local description=$2
    
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Backing up directory: $description"
        sudo cp -rp "$dir" "${BACKUP_DIR}/" 2>/dev/null || {
            echo -e "${RED}✗${NC} Failed to backup: $dir"
            return 1
        }
    else
        echo -e "${YELLOW}⚠${NC} Directory not found (skipping): $dir"
    fi
}

echo ""
echo -e "${BLUE}=== Backing up files to be modified ===${NC}"
echo ""

# Backup existing files that will be modified
backup_file "/opt/field_trainer/ft_registry.py" "Registry (will be modified)"
backup_file "/opt/field_trainer/ft_heartbeat.py" "Heartbeat server (will be modified)"
backup_file "/opt/field_trainer_main.py" "Main server script (will be modified)"

echo ""
echo -e "${BLUE}=== Backing up entire field_trainer package ===${NC}"
echo ""

# Backup entire field_trainer directory for safety
backup_directory "/opt/field_trainer" "Field Trainer package (full backup)"

echo ""
echo -e "${BLUE}=== Backing up existing courses ===${NC}"
echo ""

# Backup courses.json if it exists
backup_file "/opt/courses.json" "Courses JSON (if exists)"
backup_file "/opt/field-trainer/courses.json" "Courses JSON alt location (if exists)"

echo ""
echo -e "${BLUE}=== Backing up templates ===${NC}"
echo ""

# Backup existing templates
backup_directory "/opt/templates" "Templates directory (full backup)"

echo ""
echo -e "${BLUE}=== Creating backup manifest ===${NC}"
echo ""

# Create a manifest of what was backed up
cat > "${BACKUP_DIR}/BACKUP_MANIFEST.txt" << EOF
Field Trainer Phase 1 Backup
Created: $(date)
Backup Directory: ${BACKUP_DIR}

Files Backed Up:
================
$(ls -lah "${BACKUP_DIR}")

Original Locations:
===================
/opt/field_trainer/ft_registry.py
/opt/field_trainer/ft_heartbeat.py
/opt/field_trainer_main.py
/opt/field_trainer/ (entire directory)
/opt/templates/ (entire directory)

System Information:
===================
Hostname: $(hostname)
Kernel: $(uname -r)
Python Version: $(python3 --version)

Git Status (if available):
===========================
EOF

# Add git status if available
if [ -d "/opt/.git" ]; then
    cd /opt
    git status >> "${BACKUP_DIR}/BACKUP_MANIFEST.txt" 2>/dev/null || echo "Git not available" >> "${BACKUP_DIR}/BACKUP_MANIFEST.txt"
fi

echo -e "${GREEN}✓${NC} Backup manifest created"

echo ""
echo -e "${BLUE}=== Creating restore script ===${NC}"
echo ""

# Create restore script
cat > "${BACKUP_DIR}/restore.sh" << 'RESTORE_SCRIPT'
#!/bin/bash
# Restore script for Field Trainer Phase 1
# Run this if you need to rollback changes

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}Field Trainer Phase 1 - RESTORE${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will overwrite current files!${NC}"
echo ""
read -p "Are you sure you want to restore from backup? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

BACKUP_DIR="$(dirname "$0")"

echo ""
echo -e "${BLUE}=== Stopping services ===${NC}"
sudo systemctl stop field-trainer 2>/dev/null || echo "Service not running"

echo ""
echo -e "${BLUE}=== Restoring files ===${NC}"

# Restore modified files
if [ -f "${BACKUP_DIR}/ft_registry.py" ]; then
    echo -e "${GREEN}✓${NC} Restoring ft_registry.py"
    sudo cp -p "${BACKUP_DIR}/ft_registry.py" /opt/field_trainer/
fi

if [ -f "${BACKUP_DIR}/ft_heartbeat.py" ]; then
    echo -e "${GREEN}✓${NC} Restoring ft_heartbeat.py"
    sudo cp -p "${BACKUP_DIR}/ft_heartbeat.py" /opt/field_trainer/
fi

if [ -f "${BACKUP_DIR}/field_trainer_main.py" ]; then
    echo -e "${GREEN}✓${NC} Restoring field_trainer_main.py"
    sudo cp -p "${BACKUP_DIR}/field_trainer_main.py" /opt/
fi

echo ""
echo -e "${BLUE}=== Removing Phase 1 additions ===${NC}"

# Remove new files created in Phase 1
echo -e "${YELLOW}⚠${NC} Removing db_manager.py"
sudo rm -f /opt/field_trainer/db_manager.py

echo -e "${YELLOW}⚠${NC} Removing coach_interface.py"
sudo rm -f /opt/coach_interface.py

echo -e "${YELLOW}⚠${NC} Removing coach templates"
sudo rm -rf /opt/templates/coach

echo -e "${YELLOW}⚠${NC} Removing database (optional - keeping backup)"
# Uncomment next line to also remove database
# sudo rm -rf /opt/data

echo ""
echo -e "${GREEN}=== Restore complete ===${NC}"
echo ""
echo "To restart the system:"
echo "  sudo systemctl start field-trainer"
echo ""
echo "Database backup preserved at:"
echo "  ${BACKUP_DIR}/field_trainer.db (if exists)"

RESTORE_SCRIPT

chmod +x "${BACKUP_DIR}/restore.sh"
echo -e "${GREEN}✓${NC} Restore script created: ${BACKUP_DIR}/restore.sh"

echo ""
echo -e "${BLUE}=== Backup database if it exists ===${NC}"
echo ""

# Backup existing database if present
if [ -f "/opt/data/field_trainer.db" ]; then
    echo -e "${GREEN}✓${NC} Backing up existing database"
    sudo cp -p /opt/data/field_trainer.db "${BACKUP_DIR}/"
else
    echo -e "${YELLOW}⚠${NC} No existing database found"
fi

echo ""
echo -e "${BLUE}=== Creating quick reference ===${NC}"
echo ""

# Create quick reference card
cat > "${BACKUP_DIR}/QUICK_REFERENCE.txt" << EOF
FIELD TRAINER PHASE 1 BACKUP - QUICK REFERENCE
===============================================

Backup Location: ${BACKUP_DIR}
Backup Time: $(date)

TO RESTORE EVERYTHING:
----------------------
cd ${BACKUP_DIR}
sudo ./restore.sh

TO RESTORE SINGLE FILE:
-----------------------
sudo cp ${BACKUP_DIR}/ft_registry.py /opt/field_trainer/
sudo cp ${BACKUP_DIR}/ft_heartbeat.py /opt/field_trainer/
sudo cp ${BACKUP_DIR}/field_trainer_main.py /opt/

WHAT WAS BACKED UP:
-------------------
- Complete /opt/field_trainer/ directory
- Modified Python files (registry, heartbeat, main)
- Existing templates directory
- Database (if it existed)

NEW FILES IN PHASE 1 (not in backup):
--------------------------------------
- /opt/field_trainer/db_manager.py (NEW)
- /opt/coach_interface.py (NEW)
- /opt/templates/coach/ (NEW)
- /opt/data/field_trainer.db (NEW)

TO VIEW THIS BACKUP:
--------------------
cd ${BACKUP_DIR}
ls -lah

TO DELETE THIS BACKUP:
----------------------
sudo rm -rf ${BACKUP_DIR}

NOTES:
------
- Backup includes file permissions and timestamps
- Restore script will stop services before restoring
- Database is preserved even during restore (unless manually deleted)
EOF

echo -e "${GREEN}✓${NC} Quick reference created"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Backup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Backup location: ${YELLOW}${BACKUP_DIR}${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
ls -lh "${BACKUP_DIR}" | grep -E "\.py$|\.json$" | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo -e "${BLUE}Important files:${NC}"
echo -e "  📄 BACKUP_MANIFEST.txt - List of what was backed up"
echo -e "  📄 QUICK_REFERENCE.txt - Quick restore instructions"
echo -e "  🔧 restore.sh - Automated restore script"
echo ""
echo -e "${GREEN}You can now proceed with Phase 1 implementation!${NC}"
echo ""
echo -e "${YELLOW}To restore if needed:${NC}"
echo -e "  cd ${BACKUP_DIR}"
echo -e "  sudo ./restore.sh"
echo ""

# Create a symlink to latest backup
sudo rm -f /opt/backups/phase1_latest
sudo ln -s "${BACKUP_DIR}" /opt/backups/phase1_latest

echo -e "${BLUE}Quick access link created: /opt/backups/phase1_latest${NC}"
echo ""
