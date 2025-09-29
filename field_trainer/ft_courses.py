"""
Course loading and sane defaults for when no file is present.

Kept small and focused; registry imports this.
"""

import json
import os
from typing import Any, Dict, List

from .ft_config import COURSE_FILE


def load_courses() -> Dict[str, Any]:
    """
    Load courses from COURSE_FILE, or return default examples if missing.

    Returns:
        Dict with key "courses": List[Course]
    """
    if os.path.exists(COURSE_FILE):
        with open(COURSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # Default example data
    return {
        "courses": [
            {
                "name": "Course A",
                "description": "6-station circuit training loop",
                "stations": [
                    {"node_id": "192.168.99.100", "action": "lunge", "instruction": "Welcome! Do 10 lunges, then sprint to Device 1"},
                    {"node_id": "192.168.99.101", "action": "sprint", "instruction": "Sprint to Device 2", "distance_yards": 40},
                    {"node_id": "192.168.99.102", "action": "jog", "instruction": "Jog to Device 3", "distance_yards": 30},
                    {"node_id": "192.168.99.103", "action": "backpedal", "instruction": "Backpedal to Device 4", "distance_yards": 25},
                    {"node_id": "192.168.99.104", "action": "carioca", "instruction": "Carioca to Device 5", "distance_yards": 20},
                    {"node_id": "192.168.99.105", "action": "high_knees", "instruction": "High knees back to start", "distance_yards": 30}
                ]
            },
            {
                "name": "Course B",
                "description": "Strength circuit with Device 0",
                "stations": [
                    {"node_id": "192.168.99.100", "action": "welcome", "instruction": "Welcome! Move to Device 1"},
                    {"node_id": "192.168.99.101", "action": "pushups", "instruction": "10 pushups, then move to Device 2", "reps": 10},
                    {"node_id": "192.168.99.102", "action": "situps", "instruction": "15 situps, then return to start", "reps": 15}
                ]
            }
        ]
    }
