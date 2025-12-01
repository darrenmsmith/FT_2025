#!/usr/bin/env python3
"""
Pattern Generator for Simon Says Drills
Generates random touch sequences for pattern-based courses
"""

import random
from typing import List, Dict, Optional


class PatternGenerator:
    """Generate random patterns for Simon Says drills"""

    def __init__(self):
        self.last_pattern = None  # Track previous pattern to ensure variety

    def generate_simon_says_pattern(
        self,
        colored_devices: List[Dict],
        sequence_length: int = 4,
        allow_repeats: bool = True
    ) -> List[Dict]:
        """
        Generate a random touch pattern from colored devices

        Args:
            colored_devices: List of device dicts with 'device_id', 'device_name', 'color'
            sequence_length: Number of touches in pattern (default 4, range 3-8)
            allow_repeats: Whether same device can appear multiple times (default True)

        Returns:
            List of device dicts in the order to be touched
            Example: [
                {'device_id': '192.168.99.101', 'device_name': 'Device 1', 'color': 'red'},
                {'device_id': '192.168.99.103', 'device_name': 'Device 3', 'color': 'yellow'},
                {'device_id': '192.168.99.104', 'device_name': 'Device 4', 'color': 'blue'},
                {'device_id': '192.168.99.101', 'device_name': 'Device 1', 'color': 'red'}
            ]
        """
        if not colored_devices:
            raise ValueError("No colored devices provided for pattern generation")

        # Validate sequence length
        if sequence_length < 3:
            sequence_length = 3
        elif sequence_length > 8:
            sequence_length = 8

        # Generate random pattern
        if allow_repeats:
            # Can select same device multiple times, but NOT consecutively
            pattern = []
            for _ in range(sequence_length):
                available = [d for d in colored_devices if not pattern or d['device_id'] != pattern[-1]['device_id']]
                if not available:
                    available = colored_devices  # Fallback if only one device
                pattern.append(random.choice(available))
        else:
            # Each device can only appear once (max pattern length = number of devices)
            max_length = min(sequence_length, len(colored_devices))
            pattern = random.sample(colored_devices, k=max_length)

        # Ensure pattern is different from last pattern (for variety)
        max_attempts = 10
        attempts = 0
        while self._patterns_match(pattern, self.last_pattern) and attempts < max_attempts:
            if allow_repeats:
                # Regenerate with no-consecutive rule
                pattern = []
                for _ in range(sequence_length):
                    available = [d for d in colored_devices if not pattern or d['device_id'] != pattern[-1]['device_id']]
                    if not available:
                        available = colored_devices
                    pattern.append(random.choice(available))
            else:
                pattern = random.sample(colored_devices, k=max_length)
            attempts += 1

        # Store for next comparison
        self.last_pattern = pattern.copy()

        return pattern

    def _patterns_match(self, pattern1: Optional[List], pattern2: Optional[List]) -> bool:
        """Check if two patterns are identical"""
        if pattern1 is None or pattern2 is None:
            return False

        if len(pattern1) != len(pattern2):
            return False

        # Compare device IDs in sequence
        for i in range(len(pattern1)):
            if pattern1[i]['device_id'] != pattern2[i]['device_id']:
                return False

        return True

    def get_pattern_description(self, pattern: List[Dict]) -> str:
        """
        Get human-readable pattern description

        Args:
            pattern: List of device dicts

        Returns:
            String like "RED → YELLOW → BLUE → RED"
        """
        colors = [device['color'].upper() for device in pattern]
        return " → ".join(colors)

    def get_pattern_device_ids(self, pattern: List[Dict]) -> List[str]:
        """
        Get list of device IDs from pattern

        Args:
            pattern: List of device dicts

        Returns:
            List of device IDs in order
        """
        return [device['device_id'] for device in pattern]


# Singleton instance
pattern_generator = PatternGenerator()
