"""
Shared data models and tiny helpers.
Keep these minimal; complicated logic lives in services (registry/mesh/etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utcnow_iso() -> str:
    """Return current local time in ISO 8601 (seconds precision)."""
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class NodeInfo:
    """
    Represents a connected field device (node).
    Note: _writer is transient (socket writer) and is not serialized.
    """
    node_id: str
    ip: str
    status: str = "Unknown"
    action: Optional[str] = None
    ping_ms: Optional[int] = None
    hops: Optional[int] = None
    last_msg: Optional[str] = None
    sensors: Dict[str, Any] = field(default_factory=dict)

    # Device capability flags (reported or inferred)
    accelerometer_working: bool = False
    audio_working: bool = False

    # Battery (%), if sent by device; None until implemented
    battery_level: Optional[float] = None

    # Newer fields used by LED/audio/time features
    led_pattern: Optional[str] = None
    audio_clip: Optional[str] = None
    clock_skew_ms: Optional[int] = None

    # Transient socket writer; not included in snapshots
    _writer: Any = field(default=None, repr=False, compare=False)
