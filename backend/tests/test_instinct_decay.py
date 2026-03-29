# ruff: noqa: INP001
"""Regression tests for instinct confidence decay.

Verifies that:
1. Decay is linear (additive), not compound/multiplicative.
2. Total decay over a period is independent of tick frequency.
3. calculate_decay (read-only) and tick (mutating) produce consistent results.
4. Edge cases: disabled, no confirmation, zero confidence, future confirmation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.memory.ailearn.instincts.decay import InstinctDecayEngine
from app.memory.ailearn.instincts.instincts import Instinct


def _make_instinct(
    confidence: float = 0.8,
    decay_rate: float = 0.02,
    last_confirmed_at: datetime | None = None,
    last_decay_at: datetime | None = None,
    enabled: bool = True,
) -> Instinct:
    """Helper to create an instinct with controlled fields."""
    return Instinct(
        name="test-instinct",
        confidence=confidence,
        decay_rate=decay_rate,
        last_confirmed_at=last_confirmed_at,
        last_decay_at=last_decay_at,
        enabled=enabled,
    )


class TestLinearDecay:
    """Verify that decay is linear (not compound/multiplicative)."""

    def test_single_tick_after_two_weeks(self):
        """Confidence 0.8, decay_rate 0.02, two weeks (1 week past window).

        Expected: 0.8 - 0.02 * 1 = 0.78
        """
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        instinct = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )

        engine = InstinctDecayEngine(decay_window_days=7)
        engine.tick([instinct])

        # 1 week past the 7-day window: decay = 0.02 * 1 = 0.02
        assert instinct.confidence == pytest.approx(0.78, abs=1e-6)

    def test_many_ticks_same_result_as_single_tick(self):
        """Core regression: multiple ticks must NOT compound.

        This is the exact scenario reported by the user: calling tick()
        many times in a single day should produce the same confidence as
        calling it once covering the same total period.
        """
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        # Scenario A: single tick
        instinct_a = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )
        engine = InstinctDecayEngine(decay_window_days=7)
        engine.tick([instinct_a])

        # Scenario B: simulate many ticks across the same period
        # We simulate by manually setting last_decay_at and advancing time
        instinct_b = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )

        # 100 ticks, each covering 1/100 of the 7-day decay period
        # (from day 7 to day 14 = 1 week = 7 days of decay)
        decay_start = confirmed_at + timedelta(days=7)
        decay_duration = now - decay_start
        step = decay_duration / 100

        for i in range(100):
            tick_time = decay_start + step * (i + 1)
            decay_amount = engine._calculate_incremental_decay(instinct_b, tick_time)
            if decay_amount > 0.0:
                instinct_b.confidence = max(0.0, instinct_b.confidence - decay_amount)
                instinct_b.last_decay_at = tick_time

        # Both should produce the same confidence (within floating-point tolerance)
        assert instinct_b.confidence == pytest.approx(instinct_a.confidence, abs=1e-9)

    def test_tick_frequency_independence_high_frequency(self):
        """1000 ticks over 1 week must equal 1 tick over 1 week."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)
        engine = InstinctDecayEngine(decay_window_days=7)

        # Single tick
        single = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine.tick([single])

        # 1000 micro-ticks
        multi = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        decay_start = confirmed_at + timedelta(days=7)
        decay_duration = now - decay_start
        step = decay_duration / 1000

        for i in range(1000):
            tick_time = decay_start + step * (i + 1)
            decay_amount = engine._calculate_incremental_decay(multi, tick_time)
            if decay_amount > 0.0:
                multi.confidence = max(0.0, multi.confidence - decay_amount)
                multi.last_decay_at = tick_time

        assert multi.confidence == pytest.approx(single.confidence, abs=1e-9)


class TestCalculateDecayConsistency:
    """Verify calculate_decay is consistent with tick."""

    def test_calculate_decay_matches_tick_result(self):
        """calculate_decay should report the same amount that tick applies."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=21)  # 3 weeks ago

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        # Read-only calculation (before any tick)
        reported_decay = engine.calculate_decay(instinct)

        # 2 weeks past window: decay_rate * 2 = 0.02 * 2 = 0.04
        assert reported_decay == pytest.approx(0.04, abs=1e-6)

        # Apply via tick
        engine.tick([instinct])

        # Confidence should match
        assert instinct.confidence == pytest.approx(0.8 - 0.04, abs=1e-6)

    def test_calculate_decay_does_not_mutate(self):
        """calculate_decay must not change the instinct."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        original_confidence = instinct.confidence
        engine.calculate_decay(instinct)

        assert instinct.confidence == original_confidence
        assert instinct.last_decay_at is None


class TestNoDecayScenarios:
    """Verify no decay in expected scenarios."""

    def test_within_decay_window(self):
        """No decay if within the decay window."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=5)  # 5 days < 7 day window

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        assert engine.calculate_decay(instinct) == 0.0

        engine.tick([instinct])
        assert instinct.confidence == 0.8

    def test_disabled_instinct(self):
        """No decay for disabled instincts."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=30)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at, enabled=False)
        engine = InstinctDecayEngine(decay_window_days=7)

        assert engine.calculate_decay(instinct) == 0.0

        result = engine.tick([instinct])
        assert instinct.confidence == 0.8
        assert result == []

    def test_no_confirmed_at(self):
        """No decay if last_confirmed_at is None."""
        instinct = _make_instinct(confidence=0.8, last_confirmed_at=None)
        engine = InstinctDecayEngine(decay_window_days=7)

        assert engine.calculate_decay(instinct) == 0.0

        engine.tick([instinct])
        assert instinct.confidence == 0.8

    def test_zero_confidence(self):
        """No decay if confidence is already 0."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=30)

        instinct = _make_instinct(confidence=0.0, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        assert engine.calculate_decay(instinct) == 0.0

        engine.tick([instinct])
        assert instinct.confidence == 0.0

    def test_future_confirmation(self):
        """No decay if confirmation is in the future."""
        future = datetime.now(timezone.utc) + timedelta(days=5)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=future)
        engine = InstinctDecayEngine(decay_window_days=7)

        assert engine.calculate_decay(instinct) == 0.0


class TestConfirmAndContradict:
    """Verify confirm/contradict behavior."""

    def test_confirm_resets_decay_clock(self):
        """After confirmation, decay clock resets — no decay within new window."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        # Tick applies decay
        engine.tick([instinct])
        assert instinct.confidence < 0.8

        # Confirm resets
        engine.confirm_instinct(instinct)

        # Within new window: no decay
        assert engine.calculate_decay(instinct) == 0.0

        # last_decay_at should be reset
        assert instinct.last_decay_at is None

    def test_contradict_reduces_confidence(self):
        """Contradiction subtracts penalty from confidence."""
        instinct = _make_instinct(confidence=0.8)
        engine = InstinctDecayEngine(contradiction_penalty=0.15)

        engine.contradict_instinct(instinct)

        assert instinct.confidence == pytest.approx(0.65, abs=1e-9)

    def test_contradict_floors_at_zero(self):
        """Contradiction cannot make confidence negative."""
        instinct = _make_instinct(confidence=0.1)
        engine = InstinctDecayEngine(contradiction_penalty=0.15)

        engine.contradict_instinct(instinct)

        assert instinct.confidence == 0.0


class TestDecayCapsAtZero:
    """Verify confidence cannot go below 0."""

    def test_long_period_caps_at_zero(self):
        """After enough time, confidence reaches 0 but not below."""
        now = datetime.now(timezone.utc)
        # 100 weeks past window: decay = 0.02 * 100 = 2.0 > 0.8
        confirmed_at = now - timedelta(days=7 + 700)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        engine.tick([instinct])

        assert instinct.confidence == 0.0

    def test_calculate_decay_capped(self):
        """calculate_decay should not return more than current confidence."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=7 + 700)

        instinct = _make_instinct(confidence=0.8, last_confirmed_at=confirmed_at)
        engine = InstinctDecayEngine(decay_window_days=7)

        decay = engine.calculate_decay(instinct)
        assert decay == instinct.confidence  # capped at 0.8


class TestRegressionMultipleTicksPerDay:
    """Exact regression test for the reported bug scenario.

    User report: confidence 0.8, after 2 weeks with multiple ticks per day,
    confidence dropped to near 0. This was caused by the old formula
    ``confidence * rate * weeks`` which compounded on each tick because
    it used the *current* (already-reduced) confidence.

    With the fix (linear: ``rate * weeks``), 2 weeks should only produce
    ``0.02 * 1 = 0.02`` decay (7 days window + 7 days decay).
    """

    def test_two_weeks_multiple_ticks_per_day(self):
        """Confidence 0.8 with 10 ticks/day for 14 days should stay near 0.78."""
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)
        engine = InstinctDecayEngine(decay_window_days=7)

        instinct = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )

        # Simulate 10 ticks per day for 14 days
        decay_start = confirmed_at + timedelta(days=7)
        total_ticks = 14 * 10  # 140 ticks
        total_duration = now - decay_start  # 7 days
        step = total_duration / total_ticks

        for i in range(total_ticks):
            tick_time = decay_start + step * (i + 1)
            # During window days (first 7 days from confirmation), ticks are no-ops
            decay_amount = engine._calculate_incremental_decay(instinct, tick_time)
            if decay_amount > 0.0:
                instinct.confidence = max(0.0, instinct.confidence - decay_amount)
                instinct.last_decay_at = tick_time

        # Expected: 0.8 - (0.02 * 1 week) = 0.78
        assert instinct.confidence == pytest.approx(0.78, abs=1e-6)
        # Must NOT be near 0 (old bug)
        assert instinct.confidence > 0.7

    def test_old_formula_would_fail(self):
        """Demonstrate that the old multiplicative formula gives wrong results.

        Old formula: decay = confidence * rate * weeks (multiplicative)
        New formula: decay = rate * weeks (additive)

        With the old formula and many ticks, the confidence drops
        faster than expected because each tick uses the reduced confidence.
        """
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        # Simulate old (broken) multiplicative formula
        instinct_old = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )

        decay_start = confirmed_at + timedelta(days=7)
        total_ticks = 200
        total_duration = now - decay_start
        step = total_duration / total_ticks

        for i in range(total_ticks):
            tick_time = decay_start + step * (i + 1)
            age_days = (tick_time - confirmed_at).total_seconds() / 86400
            if age_days <= 7:
                continue

            if instinct_old.last_decay_at is not None:
                period_start = instinct_old.last_decay_at
            else:
                period_start = decay_start

            if period_start >= tick_time:
                continue

            inc_weeks = (tick_time - period_start).total_seconds() / (86400 * 7)
            # OLD (broken) formula: multiplies by current confidence
            decay_amount = instinct_old.confidence * instinct_old.decay_rate * inc_weeks
            instinct_old.confidence = max(0.0, instinct_old.confidence - decay_amount)
            instinct_old.last_decay_at = tick_time

        # Simulate new (fixed) additive formula
        instinct_new = _make_instinct(
            confidence=0.8,
            decay_rate=0.02,
            last_confirmed_at=confirmed_at,
        )
        engine = InstinctDecayEngine(decay_window_days=7)

        for i in range(total_ticks):
            tick_time = decay_start + step * (i + 1)
            decay_amount = engine._calculate_incremental_decay(instinct_new, tick_time)
            if decay_amount > 0.0:
                instinct_new.confidence = max(0.0, instinct_new.confidence - decay_amount)
                instinct_new.last_decay_at = tick_time

        # Old formula gives lower confidence (compound effect)
        assert instinct_old.confidence < instinct_new.confidence
        # New formula gives the exact expected value
        assert instinct_new.confidence == pytest.approx(0.78, abs=1e-6)

    def test_lost_last_decay_at_with_old_formula_causes_catastrophic_drop(self):
        """Demonstrate the catastrophic scenario: lost last_decay_at + old formula.

        If last_decay_at is not persisted (e.g., due to serialization gap),
        each tick re-applies decay for the FULL period. With the old
        multiplicative formula, this causes rapid confidence collapse.

        The new additive formula still suffers from re-application when
        last_decay_at is lost, but the impact per re-application is constant
        (not amplified by remaining confidence), making the degradation linear
        rather than exponential.
        """
        now = datetime.now(timezone.utc)
        confirmed_at = now - timedelta(days=14)

        # Simulate old formula with lost last_decay_at
        confidence_old = 0.8
        for _ in range(50):
            # Each "tick" recomputes from decay_start because last_decay_at=None
            weeks = 1.0  # 7 days past window
            # Old formula: confidence * rate * weeks
            decay_amount = confidence_old * 0.02 * weeks
            confidence_old = max(0.0, confidence_old - decay_amount)
            # last_decay_at NOT persisted → next tick repeats from scratch

        # Old formula: 0.8 * (1 - 0.02)^50 ≈ 0.29 (significant drop)
        assert confidence_old < 0.4  # far from the expected 0.78

        # Simulate new formula with lost last_decay_at
        confidence_new = 0.8
        for _ in range(50):
            weeks = 1.0
            # New formula: rate * weeks (independent of confidence)
            decay_amount = min(0.02 * weeks, confidence_new)
            confidence_new = max(0.0, confidence_new - decay_amount)

        # New formula: 0.8 - 50 * 0.02 = 0.8 - 1.0 = 0 (capped)
        # Still bad (because last_decay_at is lost), but the progression is
        # predictable and doesn't depend on confidence level.
        assert confidence_new == 0.0


class TestTickReturnValue:
    """Verify tick() return value semantics."""

    def test_tick_returns_decayed_instincts(self):
        """tick() should return only instincts whose confidence changed."""
        now = datetime.now(timezone.utc)
        engine = InstinctDecayEngine(decay_window_days=7)

        # One that should decay
        decaying = _make_instinct(
            confidence=0.8,
            last_confirmed_at=now - timedelta(days=14),
        )
        # One within window (no decay)
        fresh = _make_instinct(
            confidence=0.8,
            last_confirmed_at=now - timedelta(days=3),
        )

        result = engine.tick([decaying, fresh])

        assert len(result) == 1
        assert result[0] is decaying

    def test_tick_sets_last_decay_at(self):
        """tick() should set last_decay_at on decayed instincts."""
        now = datetime.now(timezone.utc)
        engine = InstinctDecayEngine(decay_window_days=7)

        instinct = _make_instinct(
            confidence=0.8,
            last_confirmed_at=now - timedelta(days=14),
        )
        assert instinct.last_decay_at is None

        engine.tick([instinct])

        assert instinct.last_decay_at is not None
