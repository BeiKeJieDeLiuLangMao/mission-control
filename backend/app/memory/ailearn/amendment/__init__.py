"""
Amendment Proposal System - ECC-style memory optimization.

Proposes and manages memory improvements based on observed patterns.
"""

from .models import AmendmentProposal, AmendmentStatus
from .proposer import AmendmentProposer

__all__ = [
    "AmendmentProposer",
    "AmendmentProposal",
    "AmendmentStatus",
]
