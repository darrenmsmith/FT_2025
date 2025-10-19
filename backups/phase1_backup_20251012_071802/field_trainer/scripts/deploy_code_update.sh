#!/bin/bash
echo "================================================"
echo "Deploying Field Trainer code to all devices"
echo "================================================"
FILES=(
    "ft_audio.py" "ft_config.py" "ft_courses.py" "ft_heartbeat.py"
    "ft_led.py" "ft_mesh.py" "ft_models.py" "ft_monitor.py"
    "ft_registry.py" "ft_version.py" "__init__.py" "field_trainer_core.py"
)
for device in 101 102 103 104 105; do
    echo "Deploying to Device $device..."
    for file in "${FILES[@]}"; do
        [ -f "/opt/field_trainer/$file" ] && scp -q /opt/field_trainer/$file pi@192.168.99.$device:/opt/field_trainer/ && echo "  ✓ $file"
    done
    echo ""
done
echo "Code deployment complete"
