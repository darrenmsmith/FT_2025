#!/usr/bin/env python3
"""
Session State Model - Manages active session state
Extracted from coach_interface.py during Phase 1 refactoring
"""

# Store active session state - supports multiple simultaneous athletes
active_session_state = {
    'session_id': None,
    'active_runs': {},  # {run_id: {'athlete_name', 'athlete_id', 'started_at', 'last_device', 'sequence_position'}}
    'device_sequence': [],  # Ordered list of device_ids in course
    'total_queued': 0  # Total athletes in queue at session start
}
