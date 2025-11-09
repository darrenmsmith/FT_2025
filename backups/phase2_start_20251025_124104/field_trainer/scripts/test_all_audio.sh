#!/bin/bash
echo "================================================"
echo "Testing audio on all Field Trainer devices"
echo "================================================"
echo ""

for device in 100 101 102 103 104 105; do
    echo "=== Device $device (192.168.99.$device) ==="
    
    if ! ping -c 1 -W 1 192.168.99.$device > /dev/null 2>&1; then
        echo "  ❌ Device not reachable"
        echo ""
        continue
    fi
    
    echo -n "  I2S Card: "
    ssh -o ConnectTimeout=5 pi@192.168.99.$device "aplay -l | grep -o 'sndrpihifiberry' || echo 'NOT FOUND'" 2>/dev/null
    
    echo -n "  Audio Files: "
    ssh -o ConnectTimeout=5 pi@192.168.99.$device "find /opt/field_trainer/audio/ -name '*.mp3' 2>/dev/null | wc -l" 2>/dev/null || echo "ERROR"
    
    echo -n "  AudioManager: "
    ssh -o ConnectTimeout=5 pi@192.168.99.$device "python3 -c \"import sys; sys.path.insert(0, '/opt/field_trainer'); from ft_audio import AudioManager; am = AudioManager(); result = am.play('sprint'); print('✅ OK' if result else '❌ FAIL')\" 2>/dev/null || echo '❌ FAIL'" 2>/dev/null
    
    echo ""
done

echo "================================================"
echo "Audio test complete"
echo "================================================"
