"""
Touch Sensor Calibration Blueprint

This blueprint provides touch sensor calibration functionality for the Field Trainer system.
"""

from flask import Blueprint

# Create the calibration blueprint
from .routes import calibration_bp, calibration_namespace

__all__ = ['calibration_bp', 'calibration_namespace']
