#!/usr/bin/env python3
"""
Field Trainer Client v5.2
Compatible with Field Trainer v5.2 Controller

This client connects to the Field Trainer controller and:
- Sends heartbeat messages with device status
- Receives action assignments
- Reports sensor data (accelerometer, audio, battery)
- Executes training actions
"""

import json
import socket
import time
import threading
import argparse
import sys
import random
import subprocess
from datetime import datetime, timezone

# Configuration
CONTROLLER_IP = "192.168.99.100"
CONTROLLER_PORT = 6000
HEARTBEAT_INTERVAL = 3  # seconds
RECONNECT_DELAY = 5     # seconds
LOG_LEVEL = "INFO"

class FieldTrainerClient:
    def __init__(self, node_id, controller_ip=CONTROLLER_IP, controller_port=CONTROLLER_PORT):
        self.node_id = node_id
        self.controller_ip = controller_ip
        self.controller_port = controller_port
        self.heartbeat_interval = HEARTBEAT_INTERVAL  # Instance variable
        self.socket = None
        self.connected = False
        self.running = True
        self.current_action = None
        self.course_status = "Inactive"
        
        # Device status
        self.status = "Ready"
        self.battery_level = 100.0
        self.accelerometer_working = True
        self.audio_working = True
        self.sensors = {}
        
        # Threading
        self.heartbeat_thread = None
        self.action_thread = None
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {self.node_id} - {message}")
        
    def connect(self):
        """Connect to the Field Trainer controller"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.controller_ip, self.controller_port))
            self.connected = True
            self.log(f"Connected to controller at {self.controller_ip}:{self.controller_port}")
            return True
        except Exception as e:
            self.log(f"Connection failed: {e}", "ERROR")
            self.connected = False
            return False
            
    def disconnect(self):
        """Disconnect from controller"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.log("Disconnected from controller")
        
    def get_ping_time(self):
        """Measure ping time to controller"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', self.controller_ip], 
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                # Extract ping time from output
                for line in result.stdout.split('\n'):
                    if 'time=' in line:
                        time_str = line.split('time=')[1].split()[0]
                        return float(time_str)
            return None
        except:
            return None
            
    def get_sensor_data(self):
        """Simulate or read actual sensor data"""
        # This would interface with actual sensors in a real device
        # For now, we'll simulate realistic data
        
        # Simulate accelerometer data
        accel_x = random.uniform(-1.0, 1.0)
        accel_y = random.uniform(-1.0, 1.0) 
        accel_z = random.uniform(0.8, 1.2)  # Gravity + small variations
        
        # Simulate other sensors
        temperature = random.uniform(20.0, 35.0)  # Celsius
        humidity = random.uniform(30.0, 70.0)     # Percentage
        
        self.sensors = {
            "accelerometer": {
                "x": round(accel_x, 3),
                "y": round(accel_y, 3), 
                "z": round(accel_z, 3)
            },
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Simulate battery drain
        if self.battery_level > 0:
            self.battery_level -= random.uniform(0.01, 0.05)
            if self.battery_level < 0:
                self.battery_level = 0
                
    def send_heartbeat(self):
        """Send heartbeat message to controller"""
        if not self.connected:
            return False
            
        try:
            # Get current system data
            ping_ms = self.get_ping_time()
            self.get_sensor_data()
            
            # Create heartbeat message matching v5.2 protocol
            message = {
                "node_id": self.node_id,
                "status": self.status,
                "ping_ms": ping_ms,
                "hops": 1,  # Assuming single hop to controller
                "sensors": self.sensors,
                "accelerometer_working": self.accelerometer_working,
                "audio_working": self.audio_working,
                "battery_level": round(self.battery_level, 1) if self.battery_level > 0 else None,
                "action": self.current_action
            }
            
            # Send JSON message with newline delimiter
            json_data = json.dumps(message) + "\n"
            self.socket.send(json_data.encode('utf-8'))
            
            # Receive response
            response_data = self.socket.recv(1024).decode('utf-8').strip()
            if response_data:
                response = json.loads(response_data)
                
                # Process controller response
                if response.get("ack"):
                    # Update action assignment
                    new_action = response.get("action")
                    if new_action != self.current_action:
                        self.log(f"Action assigned: {new_action}")
                        self.current_action = new_action
                        self.execute_action(new_action)
                        
                    # Update course status
                    self.course_status = response.get("course_status", "Inactive")
                    
                    return True
                    
        except socket.timeout:
            self.log("Heartbeat timeout", "WARNING")
            return False
        except Exception as e:
            self.log(f"Heartbeat failed: {e}", "ERROR")
            return False
            
        return False
        
    def execute_action(self, action):
        """Execute the assigned training action"""
        if not action:
            self.status = "Standby"
            return
            
        self.status = "Active"
        self.log(f"Executing action: {action}")
        
        # Start action in separate thread to avoid blocking heartbeat
        if self.action_thread and self.action_thread.is_alive():
            return  # Previous action still running
            
        self.action_thread = threading.Thread(target=self._perform_action, args=(action,))
        self.action_thread.daemon = True
        self.action_thread.start()
        
    def _perform_action(self, action):
        """Perform the actual training action"""
        try:
            if action == "welcome":
                self.log("Welcome! Ready for training.")
                self.play_audio("Welcome to training!")
                
            elif action == "lunge":
                self.log("Performing lunges...")
                self.play_audio("Do 10 lunges, then move to next device")
                self.simulate_exercise(10, "lunge")
                
            elif action == "sprint":
                self.log("Sprint to next device!")
                self.play_audio("Sprint to the next device!")
                self.simulate_movement("sprint")
                
            elif action == "jog":
                self.log("Jog to next device")
                self.play_audio("Jog to the next device")
                self.simulate_movement("jog")
                
            elif action == "backpedal":
                self.log("Backpedal to next device")
                self.play_audio("Backpedal to the next device")
                self.simulate_movement("backpedal")
                
            elif action == "carioca":
                self.log("Carioca to next device")
                self.play_audio("Carioca to the next device")
                self.simulate_movement("carioca")
                
            elif action == "high_knees":
                self.log("High knees to next device")
                self.play_audio("High knees to the next device")
                self.simulate_movement("high_knees")
                
            elif action == "pushups":
                self.log("Performing pushups...")
                self.play_audio("Do 10 pushups")
                self.simulate_exercise(10, "pushup")
                
            elif action == "situps":
                self.log("Performing situps...")
                self.play_audio("Do 15 situps")
                self.simulate_exercise(15, "situp")
                
            elif action == "burpees":
                self.log("Performing burpees...")
                self.play_audio("Do 15 burpees")
                self.simulate_exercise(15, "burpee")
                
            elif action == "mountain_climbers":
                self.log("Mountain climbers for 30 seconds")
                self.play_audio("Mountain climbers for 30 seconds")
                self.simulate_timed_exercise(30, "mountain_climber")
                
            elif action == "plank_hold":
                self.log("Plank hold for 45 seconds")
                self.play_audio("Hold plank for 45 seconds")
                self.simulate_timed_exercise(45, "plank")
                
            elif action == "jumping_jacks":
                self.log("Performing jumping jacks...")
                self.play_audio("Do 20 jumping jacks")
                self.simulate_exercise(20, "jumping_jack")
                
            else:
                self.log(f"Unknown action: {action}")
                self.play_audio(f"Unknown exercise: {action}")
                
        except Exception as e:
            self.log(f"Action execution error: {e}", "ERROR")
        finally:
            self.status = "Ready"
            
    def play_audio(self, message):
        """Play audio message (simulate for now)"""
        try:
            # In a real device, this would use audio hardware
            # For now, just log the audio message
            self.log(f"Audio: {message}")
            
            # Could use espeak or similar TTS if available:
            # subprocess.run(['espeak', message], check=False)
            
        except Exception as e:
            self.log(f"Audio playback failed: {e}", "WARNING")
            self.audio_working = False
            
    def simulate_exercise(self, reps, exercise_type):
        """Simulate performing repetitive exercises"""
        for i in range(reps):
            if not self.running:
                break
            time.sleep(0.5)  # Time per rep
            if (i + 1) % 5 == 0:  # Progress updates
                self.log(f"{exercise_type} progress: {i + 1}/{reps}")
                
    def simulate_timed_exercise(self, duration_seconds, exercise_type):
        """Simulate timed exercises"""
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            if not self.running:
                break
            time.sleep(1)
            remaining = int(duration_seconds - (time.time() - start_time))
            if remaining % 10 == 0 and remaining > 0:
                self.log(f"{exercise_type}: {remaining} seconds remaining")
                
    def simulate_movement(self, movement_type):
        """Simulate movement between devices"""
        self.log(f"Moving via {movement_type}...")
        time.sleep(random.uniform(3, 8))  # Variable movement time
        self.log(f"Movement complete")
        
    def heartbeat_loop(self):
        """Main heartbeat loop"""
        while self.running:
            if self.connected:
                if not self.send_heartbeat():
                    self.log("Heartbeat failed, attempting reconnection", "WARNING")
                    self.disconnect()
            else:
                self.log("Attempting to connect to controller...")
                if not self.connect():
                    time.sleep(RECONNECT_DELAY)
                    continue
                    
            time.sleep(self.heartbeat_interval)
            
    def start(self):
        """Start the client"""
        self.log(f"Field Trainer Client v5.2 starting...")
        self.log(f"Node ID: {self.node_id}")
        self.log(f"Controller: {self.controller_ip}:{self.controller_port}")
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Shutdown requested")
            self.stop()
            
    def stop(self):
        """Stop the client"""
        self.log("Stopping client...")
        self.running = False
        self.disconnect()
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2)
            
        self.log("Client stopped")

def main():
    parser = argparse.ArgumentParser(description='Field Trainer Client v5.2')
    parser.add_argument('--node-id', required=True, help='Device node ID (e.g., 192.168.99.101)')
    parser.add_argument('--controller-ip', default=CONTROLLER_IP, help='Controller IP address')
    parser.add_argument('--controller-port', type=int, default=CONTROLLER_PORT, help='Controller port')
    parser.add_argument('--heartbeat-interval', type=int, default=HEARTBEAT_INTERVAL, help='Heartbeat interval in seconds')
    
    args = parser.parse_args()
    
    # Create and start client
    client = FieldTrainerClient(
        node_id=args.node_id,
        controller_ip=args.controller_ip,
        controller_port=args.controller_port
    )
    
    # Update heartbeat interval for the client
    client.heartbeat_interval = args.heartbeat_interval
    
    try:
        client.start()
    except Exception as e:
        print(f"Client error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
