#!/usr/bin/env python3
"""
Field Trainer Web Interface
Simple Flask app for device testing and control
"""

from flask import Flask, render_template, jsonify, request
import subprocess
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Store active tests
active_tests = {}

class DeviceTest:
    def __init__(self, device_id):
        self.device_id = device_id
        self.running = False
        self.touches = 0
        self.start_time = None
        self.last_touch = None
        self.process = None
        
    def start(self, duration=30):
        if self.running:
            return False
        
        self.running = True
        self.touches = 0
        self.start_time = datetime.now()
        self.last_touch = None
        
        # Start test in background thread
        thread = threading.Thread(target=self._run_test, args=(duration,))
        thread.daemon = True
        thread.start()
        
        return True
    
    def _run_test(self, duration):
        cmd = f"/opt/field_trainer/scripts/test_touch_led.sh {self.device_id} {duration}"
        
        try:
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Read output and count touches
            for line in self.process.stdout:
                if '🟢 Touch detected' in line:
                    self.touches += 1
                    self.last_touch = datetime.now()
            
            self.process.wait()
            
        except Exception as e:
            print(f"Error running test on device {self.device_id}: {e}")
        finally:
            self.running = False
            self.process = None
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.running = False
            return True
        return False
    
    def get_status(self):
        return {
            'device_id': self.device_id,
            'running': self.running,
            'touches': self.touches,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_touch': self.last_touch.isoformat() if self.last_touch else None,
            'duration': (datetime.now() - self.start_time).seconds if self.start_time else 0
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices')
def get_devices():
    devices = []
    for device_num in [100, 101, 102, 103, 104, 105]:
        device_name = f"Device {device_num - 100}" if device_num == 100 else f"Device {device_num - 100}"
        status = active_tests.get(device_num, DeviceTest(device_num)).get_status()
        devices.append({
            'id': device_num,
            'name': device_name,
            'ip': f'192.168.99.{device_num}',
            'status': status
        })
    return jsonify(devices)

@app.route('/api/device/<int:device_id>/test', methods=['POST'])
def start_test(device_id):
    duration = request.json.get('duration', 30) if request.is_json else 30
    
    if device_id not in active_tests:
        active_tests[device_id] = DeviceTest(device_id)
    
    test = active_tests[device_id]
    
    if test.start(duration):
        return jsonify({'success': True, 'message': f'Test started on device {device_id}'})
    else:
        return jsonify({'success': False, 'message': 'Test already running'}), 400

@app.route('/api/device/<int:device_id>/stop', methods=['POST'])
def stop_test(device_id):
    if device_id in active_tests:
        test = active_tests[device_id]
        if test.stop():
            return jsonify({'success': True, 'message': f'Test stopped on device {device_id}'})
    
    return jsonify({'success': False, 'message': 'No test running'}), 400

@app.route('/api/device/<int:device_id>/status')
def get_device_status(device_id):
    if device_id in active_tests:
        return jsonify(active_tests[device_id].get_status())
    return jsonify({'device_id': device_id, 'running': False, 'touches': 0})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
