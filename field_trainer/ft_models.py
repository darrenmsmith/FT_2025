"""
Dataclasses and small model helpers used throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utcnow_iso() -> str:
    """UTC timestamp in ISO 8601 format (seconds precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class NodeInfo:
    """
    Represents a connected field device.

    Note: _writer is a transient handle to the socket writer; not serialized.
    """
    node_id: str
    ip: str
    status: str = "Unknown"
    action: Optional[str] = None
    ping_ms: Optional[int] = None
    hops: Optional[int] = None
    last_msg: Optional[str] = None
    sensors: Dict[str, Any] = field(default_factory=dict)
    accelerometer_working: bool = False
    audio_working: bool = False
    battery_level: Optional[float] = None
    _writer: Any = field(default=None, repr=False, compare=False)
