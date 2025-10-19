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

