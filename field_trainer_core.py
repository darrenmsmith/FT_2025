#!/usr/bin/env python3
"""
Compatibility shim exposing the public API that existing code imports.

Keeps:
- VERSION
- REGISTRY
- start_heartbeat_server()
- (optional) start_connection_monitor()

All real implementation now lives under the field_trainer/ package.
"""

from field_trainer.ft_version import VERSION
from field_trainer.ft_registry import REGISTRY
from field_trainer.ft_heartbeat import start_heartbeat_server
from field_trainer.ft_monitor import start_connection_monitor  # optional, safe import

__all__ = [
    "VERSION",
    "REGISTRY",
    "start_heartbeat_server",
    "start_connection_monitor",
]
