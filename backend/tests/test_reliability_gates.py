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
    DecisionGrade,
    EligibilityOutcome,
    FeatureAvailability,
    FeatureDependency,
    FeatureRequirement,
    ProviderIndependenceResult,
    evaluate_provider_independence,
)


def _active_dependency(
    name: str, requirement: FeatureRequirement = FeatureRequirement.OPTIONAL
) -> FeatureDependency:
    """A dependency whose evidence was actually observed."""
    return FeatureDependency(
        name=name, requirement=requirement, availability=FeatureAvailability.ACTIVE
    )


def _unavailable_dependency(
    name: str, requirement: FeatureRequirement = FeatureRequirement.OPTIONAL
) -> FeatureDependency:
    """A dependency whose evidence is missing (CoinGlass-style optional gap)."""
    return FeatureDependency(
        name=name,
        requirement=requirement,
        availability=FeatureAvailability.UNAVAILABLE,
        reason=f"{name} evidence unavailable",
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
    # The same optional CoinGlass gap, recorded identically at decision time
    # and again on replay: outcome, grade, features, and reasons all match.
    dependencies = {
        "coinglass_derivatives": _unavailable_dependency("coinglass_derivatives")
    }
    original = evaluate_provider_independence(dependencies)
    replay = evaluate_provider_independence(dependencies)

    comparison = check_replay_parity(
        candidate_id="BTCUSDT", original=original, replay=replay
    )

    assert comparison.parity is True
    assert comparison.mismatches == ()
    assert original.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert comparison.original_decision_grade is DecisionGrade.RESEARCH_ONLY
    assert comparison.replay_decision_grade is DecisionGrade.RESEARCH_ONLY


def test_replay_parity_detects_outcome_mismatch() -> None:
    original = evaluate_provider_independence(
        {"structure": _active_dependency("structure", FeatureRequirement.MANDATORY)}
    )
    replay = evaluate_provider_independence(
        {
            "structure": _unavailable_dependency(
                "structure", FeatureRequirement.MANDATORY
            )
        }
    )

    comparison = check_replay_parity(
        candidate_id="ETHUSDT", original=original, replay=replay
    )

    assert comparison.parity is False
    assert any("outcome:" in mismatch for mismatch in comparison.mismatches)
    assert any("blocking_features:" in mismatch for mismatch in comparison.mismatches)
    assert any("decision_grade:" in mismatch for mismatch in comparison.mismatches)


def test_replay_parity_detects_degraded_feature_mismatch_with_same_outcome() -> None:
    original = evaluate_provider_independence(
        {"coinglass_derivatives": _unavailable_dependency("coinglass_derivatives")}
    )
    replay = evaluate_provider_independence(
        {"coinglass_derivatives": _active_dependency("coinglass_derivatives")}
    )

    # Same outcome on both sides; only the evidence completeness differs.
    assert original.outcome is replay.outcome is EligibilityOutcome.ALERT_ELIGIBLE

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

    matching = evaluate_provider_independence(
        {"structure": _active_dependency("structure", FeatureRequirement.MANDATORY)}
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
        candidate_id="c0",
        parity=False,
        original_decision_grade=DecisionGrade.RESEARCH_ONLY,
        replay_decision_grade=DecisionGrade.RESEARCH_ONLY,
        mismatches=("outcome: mismatch",),
    )

    readiness = evaluate_release_readiness(
        freshness=freshness, replay_comparisons=[mismatched]
    )

    assert readiness.ready is False
    assert any("failed replay parity" in reason for reason in readiness.reasons)


def test_replay_parity_detects_reason_code_mismatch_with_same_outcome() -> None:
    """Same outcome, features, and grade — but a different reason code.

    The machine-readable reason attached to an unavailable dependency must
    not drift between decision and replay even when the human-readable
    reason text is unchanged, because dashboards and alerts key off codes.
    """
    original = evaluate_provider_independence(
        {
            "coinglass_derivatives": FeatureDependency(
                name="coinglass_derivatives",
                requirement=FeatureRequirement.OPTIONAL,
                availability=FeatureAvailability.UNAVAILABLE,
                reason="CoinGlass provider unavailable",
                reason_code="PROVIDER_UNAVAILABLE",
            )
        }
    )
    replay = evaluate_provider_independence(
        {
            "coinglass_derivatives": FeatureDependency(
                name="coinglass_derivatives",
                requirement=FeatureRequirement.OPTIONAL,
                availability=FeatureAvailability.UNAVAILABLE,
                reason="CoinGlass provider unavailable",
                reason_code="COINGLAS_HTTP_500",
            )
        }
    )

    assert original.outcome is replay.outcome
    assert original.decision_grade is replay.decision_grade
    assert original.degraded_optional_features == replay.degraded_optional_features

    comparison = check_replay_parity(
        candidate_id="BTCUSDT", original=original, replay=replay
    )

    assert comparison.parity is False
    assert any("reason_codes:" in mismatch for mismatch in comparison.mismatches)


def test_replay_parity_detects_decision_grade_mismatch_with_same_outcome() -> None:
    """Comparator-level: the grade itself is compared, not just the outcome.

    Results restored from storage by future callers may disagree on grade
    while agreeing on outcome and feature lists; the gate must not let that
    through.
    """
    original = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        decision_grade=DecisionGrade.RESEARCH_ONLY,
        evaluated_features=("coinglass_derivatives",),
        blocking_features=(),
        degraded_optional_features=("coinglass_derivatives",),
        reasons=(),
        reason_codes=(),
    )
    replay = ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        decision_grade=DecisionGrade.UNAVAILABLE,
        evaluated_features=(),
        blocking_features=(),
        degraded_optional_features=(),
        reasons=(),
        reason_codes=(),
    )

    comparison = check_replay_parity(
        candidate_id="SOLUSDT", original=original, replay=replay
    )

    assert comparison.parity is False
    assert any("decision_grade:" in mismatch for mismatch in comparison.mismatches)


def test_release_readiness_is_not_ready_when_candidate_grade_is_unavailable() -> None:
    """No evaluated evidence blocks release — even when parity holds.

    Freshness can pass and replay can be perfectly reproducible while still
    proving nothing: UNAVAILABLE means no dependency was evaluated at all.
    """
    samples = [FreshnessSample(candidate_id="c0", analysis_age_seconds=10.0)]
    freshness = compute_freshness_slo(samples, threshold_seconds=180.0)

    unavailable = evaluate_provider_independence({})
    comparison = check_replay_parity(
        candidate_id="c0", original=unavailable, replay=unavailable
    )
    assert comparison.parity is True

    readiness = evaluate_release_readiness(
        freshness=freshness, replay_comparisons=[comparison]
    )

    assert readiness.ready is False
    assert readiness.decision_grade_blockers == ("c0",)
    assert any("decision_grade=UNAVAILABLE" in reason for reason in readiness.reasons)
