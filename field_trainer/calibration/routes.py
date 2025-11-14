"""
Touch Sensor Calibration Flask Routes

Provides REST API endpoints and WebSocket events for touch sensor calibration.
"""

import logging
import time
import threading
from flask import Blueprint, request, jsonify
from flask_socketio import emit, Namespace
from typing import Dict, Any

from . import calibration_logic

logger = logging.getLogger(__name__)

# SocketIO instance will be set by coach_interface.py
socketio_instance = None

def set_socketio(socketio):
    """Set the SocketIO instance for use in background threads"""
    global socketio_instance
    socketio_instance = socketio

# Create blueprint
calibration_bp = Blueprint('calibration', __name__, url_prefix='/api/calibration')

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@calibration_bp.route('/devices/status', methods=['GET'])
def get_devices_status():
    """
    Get status of all devices (0-5).

    Returns:
        JSON: {
            'success': bool,
            'devices': [
                {
                    'device_num': int,
                    'name': str,
                    'ip': str,
                    'online': bool,
                    'threshold': float  # Current threshold if online
                }
            ]
        }
    """
    try:
        devices = []

        for device_num in range(6):  # Devices 0-5
            status = calibration_logic.get_device_status(device_num)

            device_info = {
                'device_num': status['device_num'],
                'name': status['name'],
                'ip': status['ip'],
                'online': status['online']
            }

            # Get threshold if device is online
            if status['online']:
                threshold_result = calibration_logic.get_current_threshold(device_num)
                if threshold_result['success']:
                    device_info['threshold'] = threshold_result['threshold']
                else:
                    device_info['threshold'] = 2.0  # Default

            devices.append(device_info)

        return jsonify({
            'success': True,
            'devices': devices
        })

    except Exception as e:
        logger.error(f"Error getting devices status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@calibration_bp.route('/device/<int:device_num>/threshold', methods=['GET'])
def get_threshold(device_num: int):
    """
    Get current threshold for specific device.

    Args:
        device_num: Device number (0-5)

    Returns:
        JSON: {
            'success': bool,
            'threshold': float,
            'error': str  # If success=False
        }
    """
    try:
        if not (0 <= device_num <= 5):
            return jsonify({
                'success': False,
                'threshold': 0.0,
                'error': 'Invalid device number. Must be 0-5.'
            }), 400

        result = calibration_logic.get_current_threshold(device_num)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting threshold for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'threshold': 0.0,
            'error': str(e)
        }), 500


@calibration_bp.route('/device/<int:device_num>/threshold', methods=['POST'])
def update_threshold(device_num: int):
    """
    Update threshold for specific device.

    Args:
        device_num: Device number (0-5)

    Body:
        {
            'threshold': float
        }

    Returns:
        JSON: {
            'success': bool,
            'message': str,
            'error': str  # If success=False
        }
    """
    try:
        if not (0 <= device_num <= 5):
            return jsonify({
                'success': False,
                'message': '',
                'error': 'Invalid device number. Must be 0-5.'
            }), 400

        data = request.get_json()
        if not data or 'threshold' not in data:
            return jsonify({
                'success': False,
                'message': '',
                'error': 'Missing threshold value'
            }), 400

        threshold = float(data['threshold'])

        result = calibration_logic.set_threshold(device_num, threshold)
        return jsonify(result)

    except ValueError as e:
        return jsonify({
            'success': False,
            'message': '',
            'error': f'Invalid threshold value: {e}'
        }), 400
    except Exception as e:
        logger.error(f"Error updating threshold for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'message': '',
            'error': str(e)
        }), 500


@calibration_bp.route('/device/<int:device_num>/reading', methods=['GET'])
def get_reading(device_num: int):
    """
    Get current accelerometer reading from device.

    Args:
        device_num: Device number (0-5)

    Returns:
        JSON: {
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
        if not (0 <= device_num <= 5):
            return jsonify({
                'success': False,
                'magnitude': 0.0,
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
                'timestamp': time.time(),
                'error': 'Invalid device number. Must be 0-5.'
            }), 400

        result = calibration_logic.get_accelerometer_reading(device_num)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting reading for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'magnitude': 0.0,
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'timestamp': time.time(),
            'error': str(e)
        }), 500


@calibration_bp.route('/device/<int:device_num>/test', methods=['POST'])
def start_test(device_num: int):
    """
    Start test mode on device.

    Args:
        device_num: Device number (0-5)

    Body:
        {
            'threshold': float,
            'duration': int  # Optional, default 10 seconds
        }

    Returns:
        JSON: {
            'success': bool,
            'message': str,
            'error': str  # If success=False
        }
    """
    try:
        if not (0 <= device_num <= 5):
            return jsonify({
                'success': False,
                'message': '',
                'error': 'Invalid device number. Must be 0-5.'
            }), 400

        data = request.get_json()
        if not data or 'threshold' not in data:
            return jsonify({
                'success': False,
                'message': '',
                'error': 'Missing threshold value'
            }), 400

        threshold = float(data['threshold'])
        duration = int(data.get('duration', 10))

        result = calibration_logic.start_test_mode(device_num, threshold, duration)
        return jsonify(result)

    except ValueError as e:
        return jsonify({
            'success': False,
            'message': '',
            'error': f'Invalid parameter: {e}'
        }), 400
    except Exception as e:
        logger.error(f"Error starting test mode for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'message': '',
            'error': str(e)
        }), 500


@calibration_bp.route('/device/<int:device_num>/test/stop', methods=['POST'])
def stop_test(device_num: int):
    """
    Stop test mode on device.

    Args:
        device_num: Device number (0-5)

    Returns:
        JSON: {
            'success': bool,
            'message': str
        }
    """
    try:
        if not (0 <= device_num <= 5):
            return jsonify({
                'success': False,
                'message': 'Invalid device number. Must be 0-5.'
            }), 400

        result = calibration_logic.stop_test_mode(device_num)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error stopping test mode for device {device_num}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================================================
# WEBSOCKET NAMESPACE FOR REAL-TIME CALIBRATION
# ============================================================================

class CalibrationNamespace(Namespace):
    """
    WebSocket namespace for calibration events.

    Events:
    - connect: Client connected
    - disconnect: Client disconnected
    - start_reading_stream: Start streaming accelerometer readings
    - stop_reading_stream: Stop streaming readings
    - start_calibration_wizard: Start full calibration process
    """

    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.reading_streams = {}  # {session_id: {'device_num': int, 'active': bool, 'thread': Thread}}
        self.calibration_sessions = {}  # {session_id: {'device_num': int, 'active': bool}}

    def on_connect(self):
        """Handle client connection"""
        logger.info(f"Client connected to calibration namespace: {request.sid}")
        emit('connected', {'message': 'Connected to calibration service'})

    def on_disconnect(self):
        """Handle client disconnection - clean up any active streams"""
        session_id = request.sid
        logger.info(f"Client disconnected from calibration namespace: {session_id}")

        # Stop any active reading streams
        if session_id in self.reading_streams:
            self.reading_streams[session_id]['active'] = False
            del self.reading_streams[session_id]

        # Stop any active calibration sessions
        if session_id in self.calibration_sessions:
            self.calibration_sessions[session_id]['active'] = False
            del self.calibration_sessions[session_id]

    def on_start_reading_stream(self, data):
        """
        Start streaming accelerometer readings.

        Args:
            data: {
                'device_num': int
            }
        """
        try:
            session_id = request.sid
            device_num = int(data.get('device_num', 0))

            if not (0 <= device_num <= 5):
                emit('error', {'message': 'Invalid device number'})
                return

            logger.info(f"Starting reading stream for device {device_num}, session {session_id}")

            # Stop any existing stream for this session
            if session_id in self.reading_streams:
                self.reading_streams[session_id]['active'] = False

            # Create new stream
            stream_info = {
                'device_num': device_num,
                'active': True,
                'thread': None
            }

            def stream_readings():
                """Thread function to stream readings"""
                while stream_info['active']:
                    try:
                        reading = calibration_logic.get_accelerometer_reading(device_num)
                        # Use socketio_instance for background thread emissions
                        if socketio_instance:
                            socketio_instance.emit('reading_update', reading, room=session_id, namespace='/calibration')
                        time.sleep(0.1)  # 10Hz update rate
                    except Exception as e:
                        logger.error(f"Error in reading stream: {e}")
                        if socketio_instance:
                            socketio_instance.emit('error', {'message': f'Reading stream error: {e}'}, room=session_id, namespace='/calibration')
                        break

            # Start streaming thread
            stream_thread = threading.Thread(target=stream_readings, daemon=True)
            stream_info['thread'] = stream_thread
            self.reading_streams[session_id] = stream_info
            stream_thread.start()

            emit('stream_started', {'device_num': device_num})

        except Exception as e:
            logger.error(f"Error starting reading stream: {e}")
            emit('error', {'message': str(e)})

    def on_stop_reading_stream(self, data):
        """
        Stop streaming accelerometer readings.
        """
        try:
            session_id = request.sid

            if session_id in self.reading_streams:
                logger.info(f"Stopping reading stream for session {session_id}")
                self.reading_streams[session_id]['active'] = False
                del self.reading_streams[session_id]
                emit('stream_stopped', {})
            else:
                emit('error', {'message': 'No active stream to stop'})

        except Exception as e:
            logger.error(f"Error stopping reading stream: {e}")
            emit('error', {'message': str(e)})

    def on_start_calibration_wizard(self, data):
        """
        Start full calibration wizard.

        Args:
            data: {
                'device_num': int,
                'tap_count': int  # Optional, default 5
            }
        """
        print(f"🔔 CALIBRATION WIZARD EVENT RECEIVED! Data: {data}")
        logger.info(f"🔔 CALIBRATION WIZARD EVENT RECEIVED! Data: {data}")
        try:
            session_id = request.sid
            device_num = int(data.get('device_num', 0))
            tap_count = int(data.get('tap_count', 5))
            print(f"   Session: {session_id}, Device: {device_num}, Tap count: {tap_count}")

            if not (0 <= device_num <= 5):
                emit('error', {'message': 'Invalid device number'})
                return

            logger.info(f"Starting calibration wizard for device {device_num}, session {session_id}")

            # Stop any existing calibration for this session
            if session_id in self.calibration_sessions:
                self.calibration_sessions[session_id]['active'] = False

            # Create new calibration session
            cal_session = {
                'device_num': device_num,
                'active': True
            }
            self.calibration_sessions[session_id] = cal_session

            def run_wizard():
                """Thread function to run calibration wizard"""
                try:
                    for progress in calibration_logic.run_calibration_wizard(device_num, tap_count):
                        if not cal_session['active']:
                            break
                        # Use socketio_instance for background thread emissions
                        if socketio_instance:
                            socketio_instance.emit('calibration_progress', progress, room=session_id, namespace='/calibration')
                except Exception as e:
                    logger.error(f"Error in calibration wizard: {e}")
                    if socketio_instance:
                        socketio_instance.emit('calibration_progress', {
                            'status': 'error',
                            'message': 'Calibration failed',
                            'error': str(e)
                        }, room=session_id, namespace='/calibration')
                finally:
                    if session_id in self.calibration_sessions:
                        del self.calibration_sessions[session_id]

            # Start calibration thread
            wizard_thread = threading.Thread(target=run_wizard, daemon=True)
            wizard_thread.start()

            emit('wizard_started', {'device_num': device_num})

        except Exception as e:
            logger.error(f"Error starting calibration wizard: {e}")
            emit('error', {'message': str(e)})


# Create namespace instance
calibration_namespace = CalibrationNamespace('/calibration')
