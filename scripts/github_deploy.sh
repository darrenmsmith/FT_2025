#!/bin/bash
set -e

# Field Trainer GitHub Deployment Script
# Pulls latest version from GitHub and deploys to Device 0

# Configuration
GITHUB_REPO="darrenmsmith/FT_2025"  # Update this with your GitHub username!
GITHUB_BRANCH="${1:-main}"                 # Default to main branch
APP_DIR="/opt/field-trainer"
TEMP_DIR="/tmp/field-trainer-deploy"
SERVICE_NAME="field-trainer"
USER="pi"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Check if git is installed
if ! command -v git &> /dev/null; then
    error "Git is not installed. Install with: sudo apt-get install git"
fi

# Check if running as correct user
if [[ $EUID -eq 0 ]]; then
   error "Please run this script as the pi user, not root"
fi

log "=== Field Trainer GitHub Deployment ==="
log "Repository: ${GITHUB_REPO}"
log "Branch: ${GITHUB_BRANCH}"
log "Deploy target: ${APP_DIR}"

# Create backup if existing installation
if [ -d "$APP_DIR" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="${APP_DIR}/data/backups/pre_github_deploy_${TIMESTAMP}.tar.gz"
    
    log "📦 Creating backup before deployment..."
    mkdir -p "${APP_DIR}/data/backups"
    sudo tar -czf "$BACKUP_FILE" -C "$APP_DIR" app config --exclude="*.pyc" --exclude="__pycache__" 2>/dev/null || true
    success "Backup created: $BACKUP_FILE"
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Clone repository
log "📥 Cloning repository from GitHub..."
cd "$TEMP_DIR"

if ! git clone --branch "$GITHUB_BRANCH" --depth 1 "https://github.com/${GITHUB_REPO}.git" field-trainer; then
    error "Failed to clone repository. Check repository name and network connection."
fi

cd field-trainer

# Verify required files exist
REQUIRED_FILES=("field_trainer_core.py" "field_trainer_web.py" "field_trainer_main.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file $file not found in repository"
    fi
done

success "Repository cloned successfully"

# Stop service if running
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    log "⏹️  Stopping Field Trainer service..."
    sudo systemctl stop "$SERVICE_NAME"
    success "Service stopped"
fi

# Create directory structure if needed
log "📁 Setting up directory structure..."
sudo mkdir -p ${APP_DIR}/{app,config,data/logs,data/backups,scripts,systemd}

# Deploy application files
log "🚀 Deploying application files..."
sudo cp field_trainer_core.py ${APP_DIR}/app/
sudo cp field_trainer_web.py ${APP_DIR}/app/
sudo cp field_trainer_main.py ${APP_DIR}/app/
sudo touch ${APP_DIR}/app/__init__.py

# Deploy configuration files (preserve existing if they exist)
if [ -f "courses.json" ]; then
    if [ -f "${APP_DIR}/config/courses.json" ]; then
        warning "Existing courses.json found - backing up"
        sudo cp ${APP_DIR}/config/courses.json ${APP_DIR}/config/courses.json.backup.$(date +%Y%m%d_%H%M%S)
    fi
    sudo cp courses.json ${APP_DIR}/config/
    success "Updated courses.json"
fi

if [ -f "field_trainer.conf" ]; then
    if [ -f "${APP_DIR}/config/field_trainer.conf" ]; then
        warning "Existing configuration found - backing up"
        sudo cp ${APP_DIR}/config/field_trainer.conf ${APP_DIR}/config/field_trainer.conf.backup.$(date +%Y%m%d_%H%M%S)
    fi
    sudo cp field_trainer.conf ${APP_DIR}/config/
    success "Updated configuration"
fi

# Deploy systemd service
if [ -f "field-trainer.service" ]; then
    sudo cp field-trainer.service ${APP_DIR}/systemd/
    sudo cp ${APP_DIR}/systemd/field-trainer.service /etc/systemd/system/
    sudo systemctl daemon-reload
    success "Updated systemd service"
fi

# Deploy scripts
if [ -f "install.sh" ]; then
    sudo cp install.sh ${APP_DIR}/scripts/
    sudo chmod +x ${APP_DIR}/scripts/install.sh
fi

if [ -f "update.sh" ]; then
    sudo cp update.sh ${APP_DIR}/scripts/
    sudo chmod +x ${APP_DIR}/scripts/update.sh
fi

if [ -f "backup.sh" ]; then
    sudo cp backup.sh ${APP_DIR}/scripts/
    sudo chmod +x ${APP_DIR}/scripts/backup.sh
fi

# Copy this deployment script for future use
sudo cp "$0" ${APP_DIR}/scripts/github_deploy.sh 2>/dev/null || true
sudo chmod +x ${APP_DIR}/scripts/github_deploy.sh 2>/dev/null || true

# Set proper ownership and permissions
log "🔐 Setting permissions..."
sudo chown -R ${USER}:${USER} ${APP_DIR}
sudo chmod +x ${APP_DIR}/app/field_trainer_main.py

# Install/update Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    log "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt --user
    success "Dependencies updated"
fi

# Create version info file
echo "Deployed from: https://github.com/${GITHUB_REPO}" | sudo tee ${APP_DIR}/VERSION > /dev/null
echo "Branch: ${GITHUB_BRANCH}" | sudo tee -a ${APP_DIR}/VERSION > /dev/null
echo "Commit: $(git rev-parse HEAD)" | sudo tee -a ${APP_DIR}/VERSION > /dev/null
echo "Deploy time: $(date)" | sudo tee -a ${APP_DIR}/VERSION > /dev/null

# Start service
log "▶️  Starting Field Trainer service..."
sudo systemctl enable "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl start "$SERVICE_NAME"

# Wait and check status
sleep 3

if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    success "Deployment completed successfully!"
    
    # Get IP address for web interface
    IP_ADDR=$(hostname -I | awk '{print $1}')
    success "🌐 Web interface: http://${IP_ADDR}:5000"
    
    # Show version info
    log "📋 Version information:"
    cat ${APP_DIR}/VERSION | sed 's/^/   /'
    
    # Show recent logs
    log "📋 Recent service logs:"
    sudo journalctl -u "$SERVICE_NAME" --no-pager -n 5
    
else
    error "Service failed to start after deployment!"
fi

# Cleanup
rm -rf "$TEMP_DIR"

log "=== GitHub Deployment Complete ==="
log "💡 To deploy updates: ./github_deploy.sh [branch-name]"
log "📋 Check status: sudo systemctl status $SERVICE_NAME"
log "📜 View logs: sudo journalctl -u $SERVICE_NAME -f"

# Create convenient update alias
echo "alias ft-update='${APP_DIR}/scripts/github_deploy.sh'" >> ~/.bashrc 2>/dev/null || true
log "💡 Tip: Run 'source ~/.bashrc' then use 'ft-update' for quick updates"
