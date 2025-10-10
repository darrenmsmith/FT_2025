#!/usr/bin/env python3
"""
MPU6050 Touch Sensor for Field Trainer
- Local touch detection with configurable sensitivity
- Independent calibration per device with local file storage
- Support for both raw values and g-force scaling
- Adaptive threshold learning for different environments
"""

import json
import time

# MPU65xx compatibility for ARMv6 devices
try:
    import smbus
except ImportError:
    import smbus2 as smbus
import threading
import os
from typing import Optional, Callable, Dict, Any

class MPU65xxTouchSensor:
    """MPU6050/6500 touch detection with calibration and adaptive learning"""
    
    def __init__(self, device_id: str, calibration_file: Optional[str] = None):
        self.device_id = device_id
        # Device-specific calibration file
        if calibration_file is None:
            device_num = device_id.split('.')[-1] if '.' in device_id else device_id
            calibration_file = f"mpu6050_cal_device{device_num}.json"
        self.calibration_file = calibration_file
        
        # Sensor configuration
        self.sensor_mode = "accelerometer"  # "accelerometer", "gyroscope", "both"
        self.use_gforce = True  # True for g-force, False for raw values
        self.threshold = 2.0  # Default threshold in g-force or raw units
        self.adaptive_enabled = True
        self.touch_callback: Optional[Callable] = None
        
        # Internal state
        self.running = False
        self.sensor_thread = None
        self.last_touch_time = 0
        self.touch_debounce = 0.5  # Minimum seconds between touches
        
        # Calibration data
        self.baseline = {"ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}
        self.calibrated = False
        
        # Hardware initialization
        self.mpu = None
        self.hardware_available = False
        
        # Statistics for adaptive learning
        self.touch_history = []
        self.false_positive_count = 0
        
        # Initialize hardware and calibration
        self._init_hardware()
        self._load_calibration()

    def _init_hardware(self):
        """Initialize MPU6050 hardware"""
        self.use_direct_i2c = False
        self.hardware_available = False
        
        try:
            # Try high-level library first
            import mpu6050
            self.mpu = mpu6050.mpu6050(0x68)
            self.use_direct_i2c = False
            self.hardware_available = True
            print(f"MPU6050 library initialized for device {self.device_id}")
            return
        except ImportError:
            print(f"MPU6050 library not available for device {self.device_id}, trying direct I2C...")
        except Exception as e:
            print(f"MPU6050 library init failed for device {self.device_id}: {e}")
        
        # Fall back to direct I2C access
        try:
            import smbus
            self.bus = smbus.SMBus(1)  # I2C bus 1
            self.mpu_address = 0x68
            
            # Test I2C communication by reading WHO_AM_I register
            who_am_i = self.bus.read_byte_data(self.mpu_address, 0x75)
            print(f"MPU6050 WHO_AM_I: 0x{who_am_i:02X} for device {self.device_id}")
            
            # Wake up MPU6050 (disable sleep mode)
            self.bus.write_byte_data(self.mpu_address, 0x6B, 0)
            
            # Test reading accelerometer data
            test_data = self.bus.read_i2c_block_data(self.mpu_address, 0x3B, 6)
            
            self.use_direct_i2c = True
            self.hardware_available = True
            print(f"MPU6050 direct I2C initialized for device {self.device_id}")
            
        except Exception as e:
            print(f"MPU6050 direct I2C init failed for device {self.device_id}: {e}")
            self.hardware_available = False
            self.use_direct_i2c = False

    def _load_calibration(self):
        """Load calibration data from file or create default"""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, 'r') as f:
                    cal_data = json.load(f)
                    self.baseline = cal_data.get("baseline", self.baseline)
                    self.threshold = cal_data.get("threshold", self.threshold)
                    self.sensor_mode = cal_data.get("sensor_mode", self.sensor_mode)
                    self.use_gforce = cal_data.get("use_gforce", self.use_gforce)
                    self.calibrated = True
                    print(f"Loaded calibration for device {self.device_id}")
            except Exception as e:
                print(f"Error loading calibration for device {self.device_id}: {e}")
                self._create_default_calibration()
        else:
            self._create_default_calibration()

    def _create_default_calibration(self):
        """Create default calibration - will auto-calibrate on first run"""
        self.calibrated = False
        print(f"No calibration found for device {self.device_id} - will auto-calibrate")

    def _save_calibration(self):
        """Save current calibration to file"""
        try:
            cal_data = {
                "device_id": self.device_id,
                "baseline": self.baseline,
                "threshold": self.threshold,
                "sensor_mode": self.sensor_mode,
                "use_gforce": self.use_gforce,
                "calibration_time": time.time(),
                "adaptive_enabled": self.adaptive_enabled
            }
            with open(self.calibration_file, 'w') as f:
                json.dump(cal_data, f, indent=2)
            print(f"Saved calibration for device {self.device_id}")
        except Exception as e:
            print(f"Error saving calibration for device {self.device_id}: {e}")

    def calibrate(self, duration: float = 3.0):
        """Perform calibration by sampling sensor at rest"""
        if not self.hardware_available:
            print(f"Cannot calibrate device {self.device_id}: hardware not available")
            return False
            
        print(f"Calibrating device {self.device_id} for {duration} seconds...")
        
        samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                if self.sensor_mode in ["accelerometer", "both"]:
                    accel = self.mpu.get_accel_data()
                    if self.sensor_mode in ["gyroscope", "both"]:
                        gyro = self.mpu.get_gyro_data()
                        sample = {**accel, **gyro}
                    else:
                        sample = accel
                else:  # gyroscope only
                    sample = self.mpu.get_gyro_data()
                
                samples.append(sample)
                time.sleep(0.01)  # 100Hz sampling
            except Exception as e:
                print(f"Calibration sample error for device {self.device_id}: {e}")
                time.sleep(0.01)
        
        if samples:
            # Calculate baseline as average
            keys = samples[0].keys()
            self.baseline = {}
            for key in keys:
                self.baseline[key] = sum(s[key] for s in samples) / len(samples)
            
            self.calibrated = True
            self._save_calibration()
            print(f"Calibration complete for device {self.device_id}: {len(samples)} samples")
            return True
        else:
            print(f"Calibration failed for device {self.device_id}: no samples collected")
            return False

    def _get_sensor_reading(self) -> Optional[Dict[str, float]]:
        """Get current sensor reading based on mode"""
        if not self.hardware_available:
            return None
            
        try:
            if self.use_direct_i2c:
                return self._get_sensor_reading_i2c()
            
            if self.sensor_mode == "accelerometer":
                return self.mpu.get_accel_data()
            elif self.sensor_mode == "gyroscope":
                return self.mpu.get_gyro_data()
            elif self.sensor_mode == "both":
                accel = self.mpu.get_accel_data()
                gyro = self.mpu.get_gyro_data()
                return {**accel, **gyro}
        except Exception as e:
            print(f"Sensor reading error for device {self.device_id}: {e}")
            return None
    def _get_sensor_reading_i2c(self) -> Optional[Dict[str, float]]:
        """Get sensor reading using direct I2C access"""
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
            
            result = {"x": accel_x, "y": accel_y, "z": accel_z}
            
            # Add gyroscope data if requested
            if self.sensor_mode in ["gyroscope", "both"]:
                # Read gyroscope data (registers 0x43 to 0x48)
                gyro_data = self.bus.read_i2c_block_data(self.mpu_address, 0x43, 6)
                
                gyro_x = self._bytes_to_int16(gyro_data[0], gyro_data[1])
                gyro_y = self._bytes_to_int16(gyro_data[2], gyro_data[3])
                gyro_z = self._bytes_to_int16(gyro_data[4], gyro_data[5])
                
                # Convert to degrees/second (LSB sensitivity: 131 LSB/°/s for ±250°/s range)
                if self.use_gforce:  # Using this flag for scaling in general
                    gyro_x = gyro_x / 131.0
                    gyro_y = gyro_y / 131.0
                    gyro_z = gyro_z / 131.0
                
                if self.sensor_mode == "gyroscope":
                    result = {"x": gyro_x, "y": gyro_y, "z": gyro_z}
                else:  # both
                    result.update({"gx": gyro_x, "gy": gyro_y, "gz": gyro_z})
            
            return result
            
        except Exception as e:
            print(f"I2C sensor reading error for device {self.device_id}: {e}")
            return None

    def _bytes_to_int16(self, high_byte: int, low_byte: int) -> int:
        """Convert two bytes to signed 16-bit integer"""
        value = (high_byte << 8) | low_byte
        # Convert to signed value
        if value >= 32768:
            value -= 65536
        return value

    def _calculate_magnitude(self, reading: Dict[str, float]) -> float:
        """Calculate magnitude of sensor reading relative to baseline"""
        if not self.calibrated or not reading:
            return 0.0
            
        try:
            # Calculate deviation from baseline
            if self.sensor_mode == "accelerometer":
                dx = reading.get('x', 0) - self.baseline.get('x', 0)
                dy = reading.get('y', 0) - self.baseline.get('y', 0) 
                dz = reading.get('z', 0) - self.baseline.get('z', 0)
                magnitude = (dx*dx + dy*dy + dz*dz) ** 0.5
            elif self.sensor_mode == "gyroscope":
                dx = reading.get('x', 0) - self.baseline.get('x', 0)
                dy = reading.get('y', 0) - self.baseline.get('y', 0)
                dz = reading.get('z', 0) - self.baseline.get('z', 0)
                magnitude = (dx*dx + dy*dy + dz*dz) ** 0.5
            else:  # both
                # Use accelerometer for primary detection
                dx = reading.get('x', 0) - self.baseline.get('x', 0)
                dy = reading.get('y', 0) - self.baseline.get('y', 0)
                dz = reading.get('z', 0) - self.baseline.get('z', 0)
                magnitude = (dx*dx + dy*dy + dz*dz) ** 0.5
                
            return magnitude
        except Exception as e:
            print(f"Magnitude calculation error for device {self.device_id}: {e}")
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
            
            # Adaptive learning
            if self.adaptive_enabled:
                self.touch_history.append({
                    "time": current_time,
                    "magnitude": magnitude,
                    "threshold": self.threshold
                })
                # Keep only recent history
                cutoff_time = current_time - 300  # 5 minutes
                self.touch_history = [h for h in self.touch_history if h["time"] > cutoff_time]
            
            return True
            
        return False

    def start_detection(self):
        """Start continuous touch detection"""
        if self.running:
            return
            
        if not self.hardware_available:
            print(f"Cannot start detection for device {self.device_id}: hardware not available")
            return
            
        # Auto-calibrate if not calibrated
        if not self.calibrated:
            print(f"Auto-calibrating device {self.device_id}...")
            if not self.calibrate():
                print(f"Auto-calibration failed for device {self.device_id}")
                return
        
        self.running = True
        self.sensor_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.sensor_thread.start()
        print(f"Touch detection started for device {self.device_id}")

    def stop_detection(self):
        """Stop continuous touch detection"""
        self.running = False
        if self.sensor_thread:
            self.sensor_thread.join(timeout=1.0)
        print(f"Touch detection stopped for device {self.device_id}")

    def _detection_loop(self):
        """Main detection loop running in separate thread"""
        while self.running:
            try:
                if self._detect_touch_event():
                    print(f"Touch detected on device {self.device_id}")
                    if self.touch_callback:
                        self.touch_callback()
                
                time.sleep(0.01)  # 100Hz detection rate
            except Exception as e:
                print(f"Detection loop error for device {self.device_id}: {e}")
                time.sleep(0.1)

    def set_touch_callback(self, callback: Callable):
        """Set function to call when touch is detected"""
        self.touch_callback = callback

    def update_threshold(self, new_threshold: float):
        """Update detection threshold"""
        self.threshold = new_threshold
        self._save_calibration()
        print(f"Updated threshold for device {self.device_id} to {new_threshold}")

    def set_sensor_mode(self, mode: str):
        """Set sensor mode: accelerometer, gyroscope, or both"""
        if mode in ["accelerometer", "gyroscope", "both"]:
            self.sensor_mode = mode
            self.calibrated = False  # Force recalibration
            self._save_calibration()
            print(f"Updated sensor mode for device {self.device_id} to {mode}")
        else:
            print(f"Invalid sensor mode for device {self.device_id}: {mode}")

    def get_status(self) -> Dict[str, Any]:
        """Get current sensor status for monitoring"""
        current_reading = self._get_sensor_reading() if self.hardware_available else None
        magnitude = self._calculate_magnitude(current_reading) if current_reading else 0.0
        
        return {
            "device_id": self.device_id,
            "hardware_available": self.hardware_available,
            "calibrated": self.calibrated,
            "running": self.running,
            "sensor_mode": self.sensor_mode,
            "use_gforce": self.use_gforce,
            "threshold": self.threshold,
            "current_magnitude": magnitude,
            "touch_detected": magnitude > self.threshold if self.calibrated else False,
            "last_touch_time": self.last_touch_time,
            "touch_history_count": len(self.touch_history),
            "calibration_file": self.calibration_file
        }

    def test_detection(self, duration: float = 5.0) -> Dict[str, Any]:
        """Test touch detection for specified duration"""
        if not self.hardware_available:
            return {"error": "Hardware not available"}
            
        print(f"Testing touch detection for device {self.device_id} for {duration} seconds...")
        
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
                    "threshold_exceeded": magnitude > self.threshold,
                    "reading": reading
                }
                test_results["samples"].append(sample)
                
                if magnitude > self.threshold:
                    test_results["touches_detected"] += 1
                    
            time.sleep(0.01)
        
        if magnitudes:
            test_results["max_magnitude"] = max(magnitudes)
            test_results["avg_magnitude"] = sum(magnitudes) / len(magnitudes)
        
        print(f"Test complete for device {self.device_id}: {test_results['touches_detected']} touches detected")
        return test_results