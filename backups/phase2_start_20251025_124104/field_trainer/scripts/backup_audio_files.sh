#!/bin/bash
BACKUP_DIR=~/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/audio_backup_$TIMESTAMP.tar.gz"
echo "Creating audio backup..."
mkdir -p $BACKUP_DIR
cd /opt/field_trainer
tar -czf $BACKUP_FILE audio/
echo "Backup created: $BACKUP_FILE"
ls -lh $BACKUP_FILE
