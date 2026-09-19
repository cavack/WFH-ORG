"""Tests for aggregate freshness SLO and replay-parity gates.

All numeric expectations are computed by hand against known inputs; no
mocks or placeholders are used. These tests exercise real percentile math
and real comparisons against PR-1's ProviderIndependenceResult.
"""

from __future__ import annotations

import pytest

from waterfallhunter.core.reliability_gates import (
    DEFAULT_MAX_ANALYSIS_AGE_SECONDS,
    FreshnessSample,
    ReplayComparison,
    check_replay_parity,
    compute_freshness_slo,
    evaluate_release_readiness,
)
from waterfallhunter.core.strict_provider_independent import (
    EligibilityOutcome,
    ProviderIndependenceResult,
)


def test_default_threshold_matches_existing_entry_decision_contract() -> None:
    assert DEFAULT_MAX_ANALYSIS_AGE_SECONDS == 180.0


def test_freshness_slo_passes_when_p95_within_threshold() -> None:
    samples = [
        FreshnessSample(candidate_id=f"c{i}", analysis_age_seconds=float(age))
        for i, age in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    ]

    result = compute_freshness_slo(samples, threshold_seconds=180.0)

    assert result.sample_count == 10
    assert result.p50_seconds == 55.0
    assert result.max_seconds == 100.0
    assert result.slo_pass is True
    assert result.breaching_candidate_ids == ()


def test_freshness_slo_fails_when_p95_exceeds_threshold() -> None:
    ages = [10.0] * 9 + [568.0]
    samples = [
        FreshnessSample(candidate_id=f"c{i}", analysis_age_seconds=age)
        for i, age in enumerate(ages)
    ]

    result = compute_freshness_slo(samples, threshold_seconds=180.0)

    assert result.max_seconds == 568.0
    assert result.slo_pass is False
    assert "c9" in result.breaching_candidate_ids


def test_freshness_slo_lists_only_breaching_candidates() -> None:
    samples = [
        FreshnessSample(candidate_id="fresh", analysis_age_seconds=50.0),
        FreshnessSample(candidate_id="stale", analysis_age_seconds=200.0),
    ]

    result = compute_freshness_slo(samples, threshold_seconds=180.0)

    assert result.breaching_candidate_ids == ("stale",)


def test_freshness_slo_rejects_empty_window() -> None:
    with pytest.raises(ValueError, match="empty sample window"):
        compute_freshness_slo([])


def test_replay_parity_matches_when_outcomes_identical() -> None:
    original = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=("coinglass_derivatives",),
        reasons=(),
    )
    replay = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=("coinglass_derivatives",),
        reasons=(),
    )

    comparison = check_replay_parity(
        candidate_id="BTCUSDT", original=original, replay=replay
    )

    assert comparison.parity is True
    assert comparison.mismatches == ()


def test_replay_parity_detects_outcome_mismatch() -> None:
    original = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=(),
        reasons=(),
    )
    replay = ProviderIndependenceResult(
        outcome=EligibilityOutcome.NOT_ALERT_GRADE,
        blocking_features=("structure",),
        degraded_optional_features=(),
        reasons=("structure: structure evidence unavailable",),
    )

    comparison = check_replay_parity(
        candidate_id="ETHUSDT", original=original, replay=replay
    )

    assert comparison.parity is False
    assert any("outcome:" in mismatch for mismatch in comparison.mismatches)
    assert any("blocking_features:" in mismatch for mismatch in comparison.mismatches)


def test_replay_parity_detects_degraded_feature_mismatch_with_same_outcome() -> None:
    original = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=("coinglass_derivatives",),
        reasons=(),
    )
    replay = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=(),
        reasons=(),
    )

    comparison = check_replay_parity(
        candidate_id="SOLUSDT", original=original, replay=replay
    )

    assert comparison.parity is False
    assert any(
        "degraded_optional_features:" in mismatch for mismatch in comparison.mismatches
    )


def test_release_readiness_is_ready_when_both_gates_pass() -> None:
    samples = [
        FreshnessSample(candidate_id=f"c{i}", analysis_age_seconds=float(age))
        for i, age in enumerate([10, 20, 30, 40, 50])
    ]
    freshness = compute_freshness_slo(samples, threshold_seconds=180.0)

    matching = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=(),
        reasons=(),
    )
    replay_comparisons = [
        check_replay_parity(candidate_id="c0", original=matching, replay=matching)
    ]

    readiness = evaluate_release_readiness(
        freshness=freshness, replay_comparisons=replay_comparisons
    )

    assert readiness.ready is True
    assert readiness.reasons == ()


def test_release_readiness_is_not_ready_when_freshness_slo_breached() -> None:
    ages = [10.0] * 9 + [568.0]
    samples = [
        FreshnessSample(candidate_id=f"c{i}", analysis_age_seconds=age)
        for i, age in enumerate(ages)
    ]
    freshness = compute_freshness_slo(samples, threshold_seconds=180.0)

    readiness = evaluate_release_readiness(freshness=freshness, replay_comparisons=[])

    assert readiness.ready is False
    assert any("freshness SLO breached" in reason for reason in readiness.reasons)


def test_release_readiness_is_not_ready_when_replay_parity_fails() -> None:
    samples = [
        FreshnessSample(candidate_id="c0", analysis_age_seconds=10.0),
    ]
    freshness = compute_freshness_slo(samples, threshold_seconds=180.0)

    mismatched = ReplayComparison(
        candidate_id="c0", parity=False, mismatches=("outcome: mismatch",)
    )

    readiness = evaluate_release_readiness(
        freshness=freshness, replay_comparisons=[mismatched]
    )

    assert readiness.ready is False
    assert any("failed replay parity" in reason for reason in readiness.reasons)
