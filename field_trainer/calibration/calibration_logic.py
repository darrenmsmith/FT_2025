"""
Touch Sensor Calibration Logic Module

This module provides core calibration functions for Field Trainer touch sensors.
It leverages the existing REGISTRY infrastructure for device communication.
"""

import time
import logging
from typing import Dict, Any, Optional, Generator
from field_trainer.ft_registry import REGISTRY

logger = logging.getLogger(__name__)


def get_device_info(device_num: int) -> Dict[str, Any]:
    """
    Get basic device information.

    Args:
        device_num: Device number (0-5)

    Returns:
        dict with keys: device_num, ip, name
    """
    device_map = {
        0: {"name": "Start", "ip": "192.168.99.100"},
        1: {"name": "Cone 1", "ip": "192.168.99.101"},
        2: {"name": "Cone 2", "ip": "192.168.99.102"},
        3: {"name": "Cone 3", "ip": "192.168.99.103"},
        4: {"name": "Cone 4", "ip": "192.168.99.104"},
        5: {"name": "Cone 5", "ip": "192.168.99.105"},
    }

    if device_num not in device_map:
        raise ValueError(f"Invalid device number: {device_num}. Must be 0-5.")

    info = device_map[device_num].copy()
    info['device_num'] = device_num
    return info


def get_device_status(device_num: int) -> Dict[str, Any]:
    """
    Check if device is online and get basic status.

    Args:
        device_num: Device number (0-5)

    Returns:
        dict: {
            'online': bool,
            'device_num': int,
            'ip': str,
            'name': str
        }
    """
    info = get_device_info(device_num)
    device_id = info['ip']

    # Device 0 is always "online" (it's the controller)
    if device_num == 0:
        return {
            'online': True,
            'device_num': device_num,
            'ip': info['ip'],
            'name': info['name']
        }

    # Check remote device status via field-trainer-server API
    online = False
    try:
        import requests
        response = requests.get('http://localhost:5000/api/state', timeout=2)
        if response.status_code == 200:
            state = response.json()
            nodes = state.get('nodes', [])
            for node in nodes:
                if node.get('ip') == device_id and node.get('status') not in ('Offline', 'Unknown'):
                    online = True
                    break
    except Exception as e:
        logger.debug(f"Failed to check device status via API: {e}")
        # Fallback to REGISTRY if API fails
        with REGISTRY.nodes_lock:
            node = REGISTRY.nodes.get(device_id)
            if node and node.status not in ('Offline', 'Unknown') and node._writer:
                online = True

    return {
        'online': online,
        'device_num': device_num,
        'ip': info['ip'],
        'name': info['name']
    }


def get_current_threshold(device_num: int) -> Dict[str, Any]:
    """
    Get current calibration threshold from device.

    For Device 0: Reads from local calibration file
    For Devices 1-5: Reads from REGISTRY (populated by heartbeat)

    Args:
        device_num: Device number (0-5)

    Returns:
        dict: {
            'success': bool,
            'threshold': float,  # Current threshold value
            'error': str  # If success=False
        }
    """
    try:
        info = get_device_info(device_num)
        device_id = info['ip']

        logger.info(f"Getting threshold for device {device_num} ({device_id})")

        # Default threshold if not available
        threshold = 2.0

        # Device 0: Read from local calibration file (gateway)
        if device_num == 0:
            try:
                import json
                import os
                # Calibration files are named by IP last octet (e.g., device100.json for 192.168.99.100)
                ip_suffix = device_id.split('.')[-1]  # "100" from "192.168.99.100"
                cal_file = f"/opt/field_trainer/config/touch_cal_device{ip_suffix}.json"
                if os.path.exists(cal_file):
                    with open(cal_file, 'r') as f:
                        cal_data = json.load(f)
                        threshold = cal_data.get('threshold', 2.0)
                        logger.info(f"Loaded threshold {threshold} from {cal_file}")
            except Exception as e:
                logger.warning(f"Could not read calibration file for device {device_num}: {e}")

        # Devices 1-5: Read from field-trainer-server API (threshold sent in heartbeat)
        else:
            try:
                import requests
                response = requests.get('http://localhost:5000/api/state', timeout=2)
                if response.status_code == 200:
                    state = response.json()
                    nodes = state.get('nodes', [])
                    for node in nodes:
                        if node.get('ip') == device_id:
                            sensors = node.get('sensors', {})
                            reported_threshold = sensors.get('touch_threshold')
                            if reported_threshold is not None:
                                threshold = float(reported_threshold)
                                logger.info(f"Loaded threshold {threshold} from API for device {device_num}")
                            else:
                                logger.warning(f"No threshold in API sensors for device {device_num}, using default")
                            break
                    else:
                        logger.warning(f"Device {device_num} not found in API state")
            except Exception as e:
                logger.warning(f"Could not read threshold from API for device {device_num}: {e}")
                # Fallback to REGISTRY if API fails
                try:
                    with REGISTRY.nodes_lock:
                        node = REGISTRY.nodes.get(device_id)
                        if node and node.sensors:
                            reported_threshold = node.sensors.get('touch_threshold')
                            if reported_threshold is not None:
                                threshold = float(reported_threshold)
                                logger.info(f"Loaded threshold {threshold} from REGISTRY fallback for device {device_num}")
                except:
                    pass

        return {
            'success': True,
            'threshold': threshold
        }

    except Exception as e:
        logger.error(f"Error getting threshold for device {device_num}: {e}")
        return {
            'success': False,
            'threshold': 0.0,
            'error': str(e)
        }


def set_threshold(device_num: int, threshold: float) -> Dict[str, Any]:
    """
    Set calibration threshold on device.

    Args:
        device_num: Device number (0-5)
        threshold: New threshold value

    Returns:
        dict: {
            'success': bool,
            'message': str,
            'error': str  # If success=False
        }
    """
    try:
        if threshold <= 0:
            return {
                'success': False,
                'message': '',
                'error': 'Threshold must be greater than 0'
            }

        info = get_device_info(device_num)
        device_id = info['ip']

        logger.info(f"Setting threshold for device {device_num} ({device_id}) to {threshold}")

        # Send calibration command to device
        command = {
            "cmd": "calibrate",
            "action": "set_threshold",
            "threshold": threshold
        }

        # For Device 0, we can update locally
        if device_num == 0:
            try:
                import json
                import os
                os.makedirs("/opt/field_trainer/config", exist_ok=True)
                # Calibration files are named by IP last octet (e.g., device100.json for 192.168.99.100)
                ip_suffix = device_id.split('.')[-1]  # "100" from "192.168.99.100"
                cal_file = f"/opt/field_trainer/config/touch_cal_device{ip_suffix}.json"

                # Read existing calibration or create new
                cal_data = {}
                if os.path.exists(cal_file):
                    with open(cal_file, 'r') as f:
                        cal_data = json.load(f)

                # Update threshold
                cal_data['threshold'] = threshold
                cal_data['device_id'] = device_id

                # Write back
                with open(cal_file, 'w') as f:
                    json.dump(cal_data, f, indent=2)

                logger.info(f"Saved threshold {threshold} to {cal_file}")

                # Also update the running sensor so the detection loop uses the new threshold immediately
                try:
                    sensor = getattr(REGISTRY, 'd0_touch_sensor', None)
                    if sensor:
                        sensor.threshold = threshold
                        logger.info(f"Updated running D0 sensor threshold to {threshold}")
                except Exception as ex:
                    logger.warning(f"Could not update running sensor threshold: {ex}")

                return {
                    'success': True,
                    'message': f'Threshold set to {threshold} for {info["name"]}'
                }
            except Exception as e:
                logger.error(f"Error writing calibration file for device {device_num}: {e}")
                return {
                    'success': False,
                    'message': '',
                    'error': f'Failed to save calibration: {e}'
                }

        # For remote devices (1-5), send command via field-trainer-server API
        try:
            import requests
            response = requests.post(
                'http://localhost:5000/api/send_command',
                json={
                    'node_id': device_id,
                    'command': command
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Successfully sent threshold command to device {device_num}")
                    return {
                        'success': True,
                        'message': f'Threshold set to {threshold} for {info["name"]}'
                    }
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"Field trainer server rejected command: {error_msg}")
                    return {
                        'success': False,
                        'message': '',
                        'error': f'Server error: {error_msg}'
                    }
            else:
                logger.error(f"API returned status code {response.status_code}")
                return {
                    'success': False,
                    'message': '',
                    'error': f'Failed to send command to {info["name"]}'
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with field trainer server: {e}")
            return {
                'success': False,
                'message': '',
                'error': f'Cannot reach field trainer server: {e}'
            }

    except Exception as e:
        logger.error(f"Error setting threshold for device {device_num}: {e}")
        return {
            'success': False,
            'message': '',
            'error': str(e)
        }


def get_accelerometer_reading(device_num: int) -> Dict[str, Any]:
    """
    Get real-time accelerometer reading from device.

    Args:
        device_num: Device number (0-5)

    Returns:
        dict: {
            'success': bool,
            'magnitude': float,
            'x': float,
            'y': float,
            'z': float,
            'timestamp': float,
            'error': str  # If success=False
        }
    """
    try:
        info = get_device_info(device_num)
        device_id = info['ip']

        logger.debug(f"Getting accelerometer reading for device {device_num} ({device_id})")

        # For Device 0, reuse the already-running sensor stored in REGISTRY.
        # Creating a new TouchSensor here conflicts with the main service's 100Hz
        # detection loop (I2C bus contention + 100ms sleep in _init_hardware).
        if device_num == 0:
            try:
                sensor = getattr(REGISTRY, 'd0_touch_sensor', None)

                if not sensor or not sensor.hardware_available:
                    return {
                        'success': False,
                        'magnitude': 0.0,
                        'x': 0.0,
                        'y': 0.0,
                        'z': 0.0,
                        'timestamp': time.time(),
                        'error': 'D0 touch sensor not available'
                    }

                # Read from cache populated by the detection loop.
                # Do NOT call _get_sensor_reading() here — the detection thread
                # owns the SMBus object and concurrent access causes silent failures.
                reading = getattr(sensor, 'last_reading', None)
                magnitude = getattr(sensor, 'last_magnitude', 0.0)
                # Drain pending touch count atomically for test mode polling
                new_touches = getattr(sensor, 'pending_touch_count', 0)
                sensor.pending_touch_count = 0
                if reading:
                    return {
                        'success': True,
                        'magnitude': magnitude,
                        'x': reading['x'],
                        'y': reading['y'],
                        'z': reading['z'],
                        'timestamp': time.time(),
                        'new_touches': new_touches
                    }
                else:
                    return {
                        'success': False,
                        'magnitude': 0.0,
                        'x': 0.0,
                        'y': 0.0,
                        'z': 0.0,
                        'timestamp': time.time(),
                        'new_touches': 0,
                        'error': 'No reading available yet'
                    }
            except Exception as e:
                logger.error(f"Error reading D0 accelerometer: {e}")
                return {
                    'success': False,
                    'magnitude': 0.0,
                    'x': 0.0,
                    'y': 0.0,
                    'z': 0.0,
                    'timestamp': time.time(),
                    'error': str(e)
                }

        # For remote devices, read latest data from REGISTRY (populated by heartbeat every 5s)
        try:
            with REGISTRY.nodes_lock:
                node = REGISTRY.nodes.get(device_id)
                if not node:
                    return {
                        'success': False,
                        'magnitude': 0.0,
                        'x': 0.0,
                        'y': 0.0,
                        'z': 0.0,
                        'timestamp': time.time(),
                        'error': 'Device not found in registry'
                    }

                if not node.sensors:
                    return {
                        'success': False,
                        'magnitude': 0.0,
                        'x': 0.0,
                        'y': 0.0,
                        'z': 0.0,
                        'timestamp': time.time(),
                        'error': 'No sensor data available from device'
                    }

                # Get accelerometer data from heartbeat (updated every 5 seconds)
                accel = node.sensors.get('accelerometer', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                magnitude = node.sensors.get('touch_magnitude', 0.0)

                # Drain pending touch count (incremented by handle_touch_event on each heartbeat touch)
                new_touches = node.sensors.get('pending_touch_count', 0)
                node.sensors['pending_touch_count'] = 0

                return {
                    'success': True,
                    'magnitude': float(magnitude),
                    'x': float(accel.get('x', 0.0)),
                    'y': float(accel.get('y', 0.0)),
                    'z': float(accel.get('z', 0.0)),
                    'timestamp': time.time(),
                    'new_touches': new_touches
                }

        except Exception as e:
            logger.error(f"Error reading sensor data from REGISTRY for device {device_num}: {e}")
            return {
                'success': False,
                'magnitude': 0.0,
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
                'timestamp': time.time(),
                'error': str(e)
            }

    except Exception as e:
        logger.error(f"Error getting accelerometer reading: {e}")
        return {
            'success': False,
            'magnitude': 0.0,
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'timestamp': time.time(),
            'error': str(e)
        }


def start_test_mode(device_num: int, threshold: float, duration: int = 10) -> Dict[str, Any]:
    """
    Start test mode on device - beep when touch detected.

    Args:
        device_num: Device number (0-5)
        threshold: Threshold to use for detection
        duration: Duration in seconds

    Returns:
        dict: {'success': bool, 'message': str, 'error': str}
    """
    try:
        info = get_device_info(device_num)
        device_id = info['ip']

        logger.info(f"Starting test mode for device {device_num} - threshold: {threshold}, duration: {duration}s")

        command = {
            "cmd": "calibrate",
            "action": "test_mode",
            "threshold": threshold,
            "duration": duration,
            "enabled": True
        }

        # For Device 0, we could start test locally
        # For remote devices, send command
        if device_num != 0:
            success = REGISTRY.send_to_node(device_id, command)
            if not success:
                return {
                    'success': False,
                    'message': '',
                    'error': f'Failed to send command to {info["name"]}'
                }

        return {
            'success': True,
            'message': f'Test mode started on {info["name"]} for {duration}s'
        }

    except Exception as e:
        logger.error(f"Error starting test mode: {e}")
        return {
            'success': False,
            'message': '',
            'error': str(e)
        }


def stop_test_mode(device_num: int) -> Dict[str, Any]:
    """
    Stop test mode on device.

    Args:
        device_num: Device number (0-5)

    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        info = get_device_info(device_num)
        device_id = info['ip']

        logger.info(f"Stopping test mode for device {device_num}")

        command = {
            "cmd": "calibrate",
            "action": "test_mode",
            "enabled": False
        }

        if device_num != 0:
            REGISTRY.send_to_node(device_id, command)

        return {
            'success': True,
            'message': f'Test mode stopped on {info["name"]}'
        }

    except Exception as e:
        logger.error(f"Error stopping test mode: {e}")
        return {
            'success': False,
            'message': str(e)
        }


def run_calibration_wizard(device_num: int, tap_count: int = 5) -> Generator[Dict[str, Any], None, None]:
    """
    Run full calibration routine (baseline + tap testing).
    Runs LOCAL calibration script on the device via SSH.
    This is a generator function that yields progress updates.

    Args:
        device_num: Device number (0-5)
        tap_count: Number of taps to collect (default: 5)

    Yields:
        Progress updates dict: {
            'status': 'baseline'|'waiting_for_tap'|'analyzing'|'complete'|'error',
            'message': str,
            'tap_number': int,
            'baseline': float,
            'tap_magnitudes': list,
            'recommended_threshold': float,
            'error': str
        }
    """
    import subprocess
    import re

    try:
        info = get_device_info(device_num)
        device_id = info['ip']

        # Device 0 is the gateway itself - run calibration script locally without SSH
        if device_num == 0:
            logger.info(f"Starting LOCAL calibration for device {device_num} ({device_id}) - local execution")
            cmd = f"cd /opt/field_trainer/scripts && python3 -u calibrate_touch.py {device_id} {tap_count}"
        else:
            # Remote devices (1-5): stop the cone service first to free I2C bus, then calibrate
            logger.info(f"Starting REMOTE calibration for device {device_num} ({device_id}) via SSH")
            stop_cmd = (
                f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no pi@{device_id} "
                f"'sudo systemctl stop field-trainer-client.service 2>/dev/null "
                f"|| sudo systemctl stop field-client.service 2>/dev/null'"
            )
            subprocess.run(stop_cmd, shell=True, timeout=10)
            logger.info(f"Stopped cone service on {device_id} before calibration")
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no pi@{device_id} 'cd /opt/field_trainer/scripts && python3 -u calibrate_touch.py {device_id} {tap_count}'"

        logger.info(f"Executing: {cmd}")

        # For Device 0, the main process runs a touch detection loop on the same I2C bus.
        # Stop it before spawning the calibration subprocess so both don't fight over the bus.
        d0_sensor_was_running = False
        if device_num == 0:
            try:
                if hasattr(REGISTRY, 'd0_touch_sensor') and REGISTRY.d0_touch_sensor:
                    if REGISTRY.d0_touch_sensor.running:
                        REGISTRY.d0_touch_sensor.stop_detection()
                        d0_sensor_was_running = True
                        logger.info("Paused D0 touch sensor for calibration")
            except Exception as e:
                logger.warning(f"Could not pause D0 touch sensor: {e}")

        try:
            # Run the script with real-time output streaming
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )

            all_output = []
            baseline = 0.0
            recommended_threshold = 0.0
            tap_magnitudes = []

            # Stream output line by line
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break

                all_output.append(line)
                line = line.strip()

                # Skip device-specific debug output
                if '[192.168.99.' in line or 'WHO_AM_I' in line or 'Loaded calibration' in line:
                    continue

                # Skip the duplicate starting message from script
                if line.startswith('🎯 Starting calibration for 192.168.99.'):
                    continue

                # Keep important lines and stream them
                if any(keyword in line for keyword in ['📊', '👆', '✓', '❌', '✅', 'Baseline:', 'Tap range:', 'Threshold:']):
                    # Yield progress update for this line
                    yield {
                        'status': 'progress',
                        'message': line,
                        'tap_number': len(tap_magnitudes),
                        'baseline': baseline,
                        'tap_magnitudes': tap_magnitudes,
                        'recommended_threshold': recommended_threshold
                    }

                    # Parse data from line
                    if 'Baseline:' in line:
                        baseline_match = re.search(r'Baseline:\s+([\d.]+)g', line)
                        if baseline_match:
                            baseline = float(baseline_match.group(1))

                    if 'Detected! Magnitude:' in line:
                        mag_match = re.search(r'Magnitude:\s+([\d.]+)g', line)
                        if mag_match:
                            tap_magnitudes.append(float(mag_match.group(1)))

                    if 'Threshold:' in line and '|' in line:
                        threshold_match = re.search(r'Threshold:\s+([\d.]+)g', line)
                        if threshold_match:
                            recommended_threshold = float(threshold_match.group(1))

            process.wait()
            full_output = ''.join(all_output)

            # Check for PASSED or FAILED
            if '✅ PASSED' in full_output:
                # For remote cones, restart their service so new threshold loads from file
                if device_num != 0:
                    try:
                        restart_cmd = (
                            f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no pi@{device_id} "
                            f"'sudo systemctl restart field-trainer-client.service 2>/dev/null "
                            f"|| sudo systemctl restart field-client.service 2>/dev/null'"
                        )
                        subprocess.run(restart_cmd, shell=True, timeout=15)
                        logger.warning(f"Restarted cone service on {device_id} to load new threshold")
                    except Exception as e:
                        logger.warning(f"Could not restart cone service on {device_id}: {e}")

                yield {
                    'status': 'complete',
                    'message': '✅ PASSED - Calibration complete!',
                    'device_num': device_num,
                    'tap_number': len(tap_magnitudes),
                    'baseline': baseline,
                    'tap_magnitudes': tap_magnitudes,
                    'recommended_threshold': recommended_threshold
                }
            else:
                # Failed
                yield {
                    'status': 'error',
                    'message': '❌ FAILED: Not all taps detected',
                    'tap_number': len(tap_magnitudes),
                    'baseline': baseline,
                    'tap_magnitudes': tap_magnitudes,
                    'recommended_threshold': 0.0,
                    'error': '❌ FAILED: Not all taps detected' if '❌ FAILED' in full_output else 'Calibration failed'
                }

        except subprocess.TimeoutExpired:
            logger.error(f"Calibration timed out after 180 seconds")
            yield {
                'status': 'error',
                'message': 'Calibration timed out after 3 minutes',
                'tap_number': 0,
                'baseline': 0.0,
                'tap_magnitudes': [],
                'recommended_threshold': 0.0,
                'error': 'Timeout'
            }

        finally:
            # Always restart D0 touch sensor if we stopped it before the subprocess
            if d0_sensor_was_running:
                try:
                    if hasattr(REGISTRY, 'd0_touch_sensor') and REGISTRY.d0_touch_sensor:
                        REGISTRY.d0_touch_sensor.start_detection()
                        logger.info("Resumed D0 touch sensor after calibration")
                except Exception as e:
                    logger.warning(f"Could not resume D0 touch sensor: {e}")

    except Exception as e:
        logger.error(f"Error in calibration wizard: {e}")
        yield {
            'status': 'error',
            'message': 'Calibration failed',
            'tap_number': 0,
            'baseline': 0.0,
            'tap_magnitudes': [],
            'recommended_threshold': 0.0,
            'error': str(e)
        }
