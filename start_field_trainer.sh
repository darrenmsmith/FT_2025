#!/bin/bash
# Field Trainer Startup Script with Audio Enabled

export FIELD_TRAINER_ENABLE_SERVER_AUDIO=1
export FIELD_TRAINER_AUDIO_VOLUME=80

cd /opt
exec python3 -u field_trainer_main.py --host 0.0.0.0 --port 5000 --debug 0
