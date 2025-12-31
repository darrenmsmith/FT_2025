#!/usr/bin/env python3
"""
MPU6500 Touch Sensor for Field Trainer
- Local touch detection with configurable sensitivity
- Independent calibration per device with local file storage
- Support for multiple I2C addresses (0x68, 0x71, 0x73)
- Integration with LED system for visual feedback
- Touch event reporting to Device 0 via heartbeat
"""

import json
import time
import os
import threading
from typing import Optional, Callable, Dict, Any

try:
    import smbus
except ImportError:
    try:
        import smbus2 as smbus
    except ImportError:
        smbus = None


class TouchSensor:
    """MPU6500 touch detection with calibration and adaptive learning"""
    
    # Possible MPU6500 I2C addresses
    POSSIBLE_ADDRESSES = [0x68, 0x69, 0x71, 0x73]
    
    def __init__(self, device_id: str, config_dir: str = "/opt/field_trainer/config"):
        self.device_id = device_id
        self.config_dir = config_dir
        
        # Device-specific calibration file
        device_num = device_id.split('.')[-1] if '.' in device_id else device_id
        self.calibration_file = os.path.join(config_dir, f"touch_cal_device{device_num}.json")
        
        # Sensor configuration
        self.sensor_mode = "accelerometer"  # Primary mode for touch detection
        self.use_gforce = True  # Use g-force scaling
        self.threshold = 2.0  # Default threshold in g-force
        self.touch_callback: Optional[Callable] = None
        
        # Internal state
        self.running = False
        self.sensor_thread = None
        self.last_touch_time = 0
        # D0 needs lower debounce for responsive pattern completion
        self.touch_debounce = 0.1 if device_id == "192.168.99.100" else 1.0  # Minimum seconds between touches
        
        # Calibration data
        self.baseline = {"x": 0, "y": 0, "z": 0}
        self.calibrated = False
        
        # Hardware initialization
        self.bus = None
        self.mpu_address = None
        self.hardware_available = False
        
        # Touch event tracking
        self.touch_count = 0
        self.touch_history = []
        
        # Initialize hardware and calibration
        self._init_hardware()
        self._load_calibration()

    def _init_hardware(self):
        """Initialize MPU6500 hardware - try multiple I2C addresses"""
        if smbus is None:
            print(f"[{self.device_id}] smbus library not available")
            return
        
        try:
            self.bus = smbus.SMBus(1)  # I2C bus 1
            
            # Try each possible address
            for addr in self.POSSIBLE_ADDRESSES:
                try:
                    # Wake up sensor
                    self.bus.write_byte_data(addr, 0x6B, 0)
                    time.sleep(0.1)
                    
                    # Read WHO_AM_I register
                    who_am_i = self.bus.read_byte_data(addr, 0x75)
                    
                    # Test reading accelerometer
                    test_data = self.bus.read_i2c_block_data(addr, 0x3B, 6)
                    
                    # Success!
                    self.mpu_address = addr
                    self.hardware_available = True
                    sensor_type = "MPU6050" if who_am_i == 0x68 else "MPU6500"
                    print(f"[{self.device_id}] {sensor_type} initialized at 0x{addr:02X} (WHO_AM_I: 0x{who_am_i:02X})")
                    return
                    
                except Exception:
                    continue
            
            print(f"[{self.device_id}] No MPU6500 found at any address")
            
        except Exception as e:
            print(f"[{self.device_id}] Hardware init error: {e}")

    def _load_calibration(self):
        """Load calibration data from file"""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, 'r') as f:
                    cal_data = json.load(f)
                    self.baseline = cal_data.get("baseline", self.baseline)
                    self.threshold = cal_data.get("threshold", self.threshold)
                    self.sensor_mode = cal_data.get("sensor_mode", self.sensor_mode)
                    self.use_gforce = cal_data.get("use_gforce", self.use_gforce)
                    self.calibrated = True
                    print(f"[{self.device_id}] Loaded calibration (threshold: {self.threshold})")
            except Exception as e:
                print(f"[{self.device_id}] Error loading calibration: {e}")
                self.calibrated = False
        else:
            print(f"[{self.device_id}] No calibration found - needs calibration")
            self.calibrated = False

    def _save_calibration(self):
        """Save current calibration to file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            cal_data = {
                "device_id": self.device_id,
                "baseline": self.baseline,
                "threshold": self.threshold,
                "sensor_mode": self.sensor_mode,
                "use_gforce": self.use_gforce,
                "calibration_time": time.time(),
                "mpu_address": f"0x{self.mpu_address:02X}" if self.mpu_address else None
            }
            with open(self.calibration_file, 'w') as f:
                json.dump(cal_data, f, indent=2)
            print(f"[{self.device_id}] Calibration saved")
        except Exception as e:
            print(f"[{self.device_id}] Error saving calibration: {e}")

    def calibrate(self, duration: float = 3.0) -> bool:
        """Perform calibration by sampling sensor at rest"""
        if not self.hardware_available:
            print(f"[{self.device_id}] Cannot calibrate: hardware not available")
            return False
        
        print(f"[{self.device_id}] Calibrating for {duration} seconds (keep still)...")
        
        samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                reading = self._get_sensor_reading()
                if reading:
                    samples.append(reading)
                time.sleep(0.01)  # 100Hz sampling
            except Exception as e:
                print(f"[{self.device_id}] Calibration sample error: {e}")
                time.sleep(0.01)
        
        if samples and len(samples) > 10:
            # Calculate baseline as average
            self.baseline = {
                'x': sum(s['x'] for s in samples) / len(samples),
                'y': sum(s['y'] for s in samples) / len(samples),
                'z': sum(s['z'] for s in samples) / len(samples)
            }
            
            self.calibrated = True
            self._save_calibration()
            print(f"[{self.device_id}] Calibration complete: {len(samples)} samples")
            print(f"[{self.device_id}] Baseline: x={self.baseline['x']:.2f}, y={self.baseline['y']:.2f}, z={self.baseline['z']:.2f}")
            return True
        else:
            print(f"[{self.device_id}] Calibration failed: insufficient samples")
            return False

    def _get_sensor_reading(self) -> Optional[Dict[str, float]]:
        """Get current accelerometer reading via I2C"""
        if not self.hardware_available or not self.bus or not self.mpu_address:
            return None
        
        try:
            # Read accelerometer data (registers 0x3B to 0x40)
            accel_data = self.bus.read_i2c_block_data(self.mpu_address, 0x3B, 6)
            
            # Convert to signed 16-bit values
            accel_x = self._bytes_to_int16(accel_data[0], accel_data[1])
            accel_y = self._bytes_to_int16(accel_data[2], accel_data[3])
            accel_z = self._bytes_to_int16(accel_data[4], accel_data[5])
            
            # Convert to g-force (LSB sensitivity: 16384 LSB/g for ±2g range)
            if self.use_gforce:
                accel_x = accel_x / 16384.0
                accel_y = accel_y / 16384.0
                accel_z = accel_z / 16384.0
            
            return {"x": accel_x, "y": accel_y, "z": accel_z}
            
        except Exception as e:
            print(f"[{self.device_id}] Sensor reading error: {e}")
            return None

    def _bytes_to_int16(self, high_byte: int, low_byte: int) -> int:
        """Convert two bytes to signed 16-bit integer"""
        value = (high_byte << 8) | low_byte
        if value >= 32768:
            value -= 65536
        return value

    def _calculate_magnitude(self, reading: Dict[str, float]) -> float:
        """Calculate magnitude of sensor reading relative to baseline"""
        if not self.calibrated or not reading:
            return 0.0
        
        try:
            dx = reading['x'] - self.baseline['x']
            dy = reading['y'] - self.baseline['y']
            dz = reading['z'] - self.baseline['z']
            magnitude = (dx*dx + dy*dy + dz*dz) ** 0.5
            return magnitude
        except Exception as e:
            print(f"[{self.device_id}] Magnitude calculation error: {e}")
            return 0.0

    def _detect_touch_event(self) -> bool:
        """Main touch detection logic"""
        reading = self._get_sensor_reading()
        if not reading:
            return False
        
        magnitude = self._calculate_magnitude(reading)
        
        # Check for touch based on threshold
        if magnitude > self.threshold:
            current_time = time.time()
            
            # Debounce check
            if current_time - self.last_touch_time < self.touch_debounce:
                return False
            
            self.last_touch_time = current_time
            self.touch_count += 1
            
            # Record touch event
            self.touch_history.append({
                "time": current_time,
                "magnitude": magnitude,
                "threshold": self.threshold
            })
            
            # Keep only recent history (last 5 minutes)
            cutoff_time = current_time - 300
            self.touch_history = [h for h in self.touch_history if h["time"] > cutoff_time]
            
            return True
        
        return False

    def start_detection(self):
        """Start continuous touch detection"""
        if self.running:
            return
        
        if not self.hardware_available:
            print(f"[{self.device_id}] Cannot start: hardware not available")
            return
        
        # Auto-calibrate if not calibrated
        if not self.calibrated:
            print(f"[{self.device_id}] Auto-calibrating...")
            if not self.calibrate():
                print(f"[{self.device_id}] Auto-calibration failed")
                return
        
        self.running = True
        self.sensor_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.sensor_thread.start()
        print(f"[{self.device_id}] Touch detection started")

    def stop_detection(self):
        """Stop continuous touch detection"""
        self.running = False
        if self.sensor_thread:
            self.sensor_thread.join(timeout=1.0)
        print(f"[{self.device_id}] Touch detection stopped")

    def _detection_loop(self):
        """Main detection loop running in separate thread"""
        while self.running:
            try:
                if self._detect_touch_event():
                    print(f"[{self.device_id}] Touch detected (count: {self.touch_count})")
                    if self.touch_callback:
                        self.touch_callback()
                
                time.sleep(0.01)  # 100Hz detection rate
            except Exception as e:
                print(f"[{self.device_id}] Detection loop error: {e}")
                time.sleep(0.1)

    def set_touch_callback(self, callback: Callable):
        """Set function to call when touch is detected"""
        self.touch_callback = callback

    def update_threshold(self, new_threshold: float):
        """Update detection threshold"""
        self.threshold = new_threshold
        self._save_calibration()
        print(f"[{self.device_id}] Threshold updated to {new_threshold}")

    def get_status(self) -> Dict[str, Any]:
        """Get current sensor status"""
        current_reading = self._get_sensor_reading() if self.hardware_available else None
        magnitude = self._calculate_magnitude(current_reading) if current_reading else 0.0
        
        return {
            "device_id": self.device_id,
            "hardware_available": self.hardware_available,
            "mpu_address": f"0x{self.mpu_address:02X}" if self.mpu_address else None,
            "calibrated": self.calibrated,
            "running": self.running,
            "threshold": self.threshold,
            "current_magnitude": magnitude,
            "touch_detected": magnitude > self.threshold if self.calibrated else False,
            "touch_count": self.touch_count,
            "last_touch_time": self.last_touch_time,
            "calibration_file": self.calibration_file
        }

    def test_detection(self, duration: float = 5.0) -> Dict[str, Any]:
        """Test touch detection for specified duration"""
        if not self.hardware_available:
            return {"error": "Hardware not available"}
        
        print(f"[{self.device_id}] Testing for {duration} seconds...")
        
        test_results = {
            "device_id": self.device_id,
            "test_duration": duration,
            "samples": [],
            "touches_detected": 0,
            "max_magnitude": 0.0,
            "avg_magnitude": 0.0
        }
        
        start_time = time.time()
        magnitudes = []
        
        while time.time() - start_time < duration:
            reading = self._get_sensor_reading()
            if reading:
                magnitude = self._calculate_magnitude(reading)
                magnitudes.append(magnitude)
                
                sample = {
                    "time": time.time() - start_time,
                    "magnitude": magnitude,
                    "threshold_exceeded": magnitude > self.threshold
                }
                test_results["samples"].append(sample)
                
                if magnitude > self.threshold:
                    test_results["touches_detected"] += 1
            
            time.sleep(0.01)
        
        if magnitudes:
            test_results["max_magnitude"] = max(magnitudes)
            test_results["avg_magnitude"] = sum(magnitudes) / len(magnitudes)
        
        print(f"[{self.device_id}] Test complete: {test_results['touches_detected']} touches")
        print(f"[{self.device_id}] Max magnitude: {test_results['max_magnitude']:.2f}")
        return test_results

    def reset_touch_count(self):
        """Reset touch counter"""
        self.touch_count = 0
        self.touch_history = []
        print(f"[{self.device_id}] Touch count reset")
