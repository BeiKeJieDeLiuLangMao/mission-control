"""
Instincts System - ECC auto-applied high-confidence patterns.

Automatically applies high-confidence patterns without user intervention.
"""

from .auto_applier import InstinctApplier
from .decay import InstinctDecayEngine
from .instincts import Instinct, InstinctRegistry

__all__ = [
    "Instinct",
    "InstinctRegistry",
    "InstinctApplier",
    "InstinctDecayEngine",
]
