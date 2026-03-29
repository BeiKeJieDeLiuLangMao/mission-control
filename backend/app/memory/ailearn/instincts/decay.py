"""
Instinct decay engine — confidence decay over time.

ECC-style decay:
- No confirmation for decay_window → weekly decay_rate applied
- Confirmation → no decay, clock resets
- Contradiction → penalty applied immediately

IMPORTANT: tick() uses incremental decay — only the time elapsed since the last
tick (or since the decay window expired, whichever is later) is used to compute
the decay amount. This prevents the compounding double-decay bug where repeated
tick() calls would each re-apply the full cumulative decay from the original
confirmation date.
"""

from datetime import datetime, timezone, timedelta
from typing import List

from .instincts import Instinct


class InstinctDecayEngine:
    """
    Computes confidence decay for instincts based on time since last confirmation.

    Incremental decay formula (used by tick()):
        period_start = max(last_decay_at, last_confirmed_at + decay_window)
        period_end   = now
        incremental_weeks = (period_end - period_start) / 7 days
        decay_amount = confidence * decay_rate * incremental_weeks

    Absolute decay formula (used by calculate_decay() for read-only queries):
        age = now - last_confirmed_at
        if age > decay_window:
            total_weeks = (age - decay_window) / 7 days
            decay_amount = confidence * decay_rate * total_weeks
    """

    def __init__(
        self,
        decay_window_days: int = 7,
        default_decay_rate: float = 0.02,
        contradiction_penalty: float = 0.15,
    ):
        """
        Initialize decay engine.

        Args:
            decay_window_days: Days without confirmation before decay starts.
            default_decay_rate: Weekly decay rate (fraction of confidence lost per week).
            contradiction_penalty: Fraction to subtract on contradiction.
        """
        self.decay_window_days = decay_window_days
        self.default_decay_rate = default_decay_rate
        self.contradiction_penalty = contradiction_penalty

    def calculate_decay(self, instinct: Instinct) -> float:
        """
        Calculate the *total absolute* decay amount for an instinct (read-only).

        This is a read-only query: it does NOT mutate the instinct and computes
        the total decay that would have accumulated since the decay window expired.
        Use this for display / reporting purposes.

        For applying decay (mutating confidence), use tick() instead.

        Args:
            instinct: Instinct to evaluate.

        Returns:
            Decay amount (0.0 if no decay applies).
        """
        # Disabled instincts are handled separately (skip decay)
        if not instinct.enabled:
            return 0.0

        # No confirmed date → cannot compute age → no decay
        if instinct.last_confirmed_at is None:
            return 0.0

        # Future confirmation date → no decay
        now = datetime.now(timezone.utc)
        if instinct.last_confirmed_at > now:
            return 0.0

        # Zero confidence → nothing to decay
        if instinct.confidence <= 0.0:
            return 0.0

        age = now - instinct.last_confirmed_at
        age_days = age.total_seconds() / 86400

        if age_days <= self.decay_window_days:
            return 0.0

        # Number of weeks beyond the decay window
        weeks = (age_days - self.decay_window_days) / 7.0
        decay = instinct.confidence * instinct.decay_rate * weeks

        return min(decay, instinct.confidence)

    def _calculate_incremental_decay(self, instinct: Instinct, now: datetime) -> float:
        """
        Calculate the *incremental* decay since the last tick (or decay window edge).

        Only the time period that has NOT yet been accounted for by a previous
        tick() call is used in the computation. This prevents compounding.

        Args:
            instinct: Instinct to evaluate.
            now: Current UTC timestamp (passed in for consistency within a tick batch).

        Returns:
            Incremental decay amount (0.0 if no decay applies).
        """
        if not instinct.enabled:
            return 0.0

        if instinct.last_confirmed_at is None:
            return 0.0

        if instinct.last_confirmed_at > now:
            return 0.0

        if instinct.confidence <= 0.0:
            return 0.0

        age_days = (now - instinct.last_confirmed_at).total_seconds() / 86400

        if age_days <= self.decay_window_days:
            return 0.0

        # The earliest point at which decay starts for this instinct
        decay_start = instinct.last_confirmed_at + timedelta(days=self.decay_window_days)

        # The period start is the later of: decay_start or last_decay_at
        if instinct.last_decay_at is not None and instinct.last_decay_at > decay_start:
            period_start = instinct.last_decay_at
        else:
            period_start = decay_start

        # If period_start is in the future or at/after now, no new decay to apply
        if period_start >= now:
            return 0.0

        incremental_weeks = (now - period_start).total_seconds() / (86400 * 7)
        decay = instinct.confidence * instinct.decay_rate * incremental_weeks

        return min(decay, instinct.confidence)

    def confirm_instinct(self, instinct: Instinct) -> None:
        """
        Record a confirmation for an instinct (resets the decay clock).

        Args:
            instinct: Instinct that was confirmed.
        """
        instinct.last_confirmed_at = datetime.now(timezone.utc)
        instinct.last_contradicted_at = None
        # Reset decay tracking so next tick starts fresh from the new window
        instinct.last_decay_at = None

    def contradict_instinct(self, instinct: Instinct) -> None:
        """
        Record a contradiction and reduce instinct confidence.

        Args:
            instinct: Instinct that was contradicted.
        """
        instinct.last_contradicted_at = datetime.now(timezone.utc)
        instinct.confidence = max(0.0, instinct.confidence - self.contradiction_penalty)

    def tick(self, instincts: List[Instinct]) -> List[Instinct]:
        """
        Apply incremental decay to a batch of instincts.

        Each call only applies decay for the time period since the last tick()
        (or since the decay window expired, for the first tick). This makes
        tick() safe to call at any frequency without compounding errors.

        Args:
            instincts: List of instincts to evaluate.

        Returns:
            List of instincts whose confidence changed.
        """
        now = datetime.now(timezone.utc)
        decayed: List[Instinct] = []

        for instinct in instincts:
            if not instinct.enabled:
                continue

            decay_amount = self._calculate_incremental_decay(instinct, now)
            if decay_amount > 0.0:
                instinct.confidence = max(0.0, instinct.confidence - decay_amount)
                instinct.last_decay_at = now
                decayed.append(instinct)

        return decayed
