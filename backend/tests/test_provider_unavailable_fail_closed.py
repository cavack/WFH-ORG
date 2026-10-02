"""Fail-closed regressions for provider availability, grading, and replay facts.

Every test below encodes a rule that must hold for the system to be trustworthy
to a human operator. The rules are:

1. STRICT alert eligibility must never require CoinGlass to be available.
2. An unavailable provider or feature must be reported as ``UNAVAILABLE`` with a
   machine-readable reason, never as an assumed neutral or zero value.
3. Evidence that cannot be established must never be graded ``DECISION_GRADE``.
4. Replay must never fabricate a zero capture timestamp or a zero reference
   price in order to look complete. It must report the gap and fail closed.
"""
from __future__ import annotations

from waterfallhunter.core.feature_replay import (
    FeatureReplayEngine,
    resolve_reference_price,
)
from waterfallhunter.core.strict_provider_independent import (
    PROVIDER_UNAVAILABLE,
    DecisionGrade,
    FeatureAvailability,
    FeatureDependency,
    FeatureRequirement,
    coinglass_dependency,
    evaluate_provider_independence,
)


def _dependency(
    name: str,
    requirement: FeatureRequirement,
    availability: FeatureAvailability,
    reason: str | None = None,
) -> FeatureDependency:
    return FeatureDependency(
        name=name,
        requirement=requirement,
        availability=availability,
        reason=reason,
    )


def test_coinglass_unavailable_never_blocks_strict_and_degrades_to_research_only() -> None:
    """CoinGlass is an enhancement: its absence must not block a STRICT candidate."""
    result = evaluate_provider_independence(
        {
            "coinglass_derivatives": coinglass_dependency(available=False),
            "structure": _dependency(
                "structure", FeatureRequirement.MANDATORY, FeatureAvailability.ACTIVE
            ),
        }
    )
    assert result.outcome.value == "ALERT_ELIGIBLE"
    assert result.blocking_features == ()
    assert result.degraded_optional_features == ("coinglass_derivatives",)
    assert result.decision_grade is DecisionGrade.RESEARCH_ONLY


def test_complete_evidence_is_decision_grade() -> None:
    result = evaluate_provider_independence(
        {
            "structure": _dependency(
                "structure", FeatureRequirement.MANDATORY, FeatureAvailability.ACTIVE
            ),
            "coinglass_derivatives": coinglass_dependency(available=True),
        }
    )
    assert result.decision_grade is DecisionGrade.DECISION_GRADE
    assert result.reason_codes == ()


def test_mandatory_gap_is_research_only_and_never_decision_grade() -> None:
    result = evaluate_provider_independence(
        {
            "structure": _dependency(
                "structure",
                FeatureRequirement.MANDATORY,
                FeatureAvailability.UNAVAILABLE,
                "structure evidence unavailable",
            ),
        }
    )
    assert result.decision_grade is DecisionGrade.RESEARCH_ONLY
    assert result.blocking_features == ("structure",)
    assert result.reason_codes == (f"structure: {PROVIDER_UNAVAILABLE}",)


def test_unavailable_without_explicit_code_still_reports_provider_unavailable() -> None:
    """A caller that forgets the code must not be able to hide the gap."""
    result = evaluate_provider_independence(
        {
            "structure": _dependency(
                "structure",
                FeatureRequirement.MANDATORY,
                FeatureAvailability.UNAVAILABLE,
                "structure provider returned nothing",
            ),
        }
    )
    assert result.reason_codes == (f"structure: {PROVIDER_UNAVAILABLE}",)


def test_nothing_evaluable_fails_closed_to_unavailable() -> None:
    """No evaluated evidence can never be alert-grade; correctness is unknown."""
    result = evaluate_provider_independence({})
    assert result.outcome.value == "NOT_ALERT_GRADE"
    assert result.decision_grade is DecisionGrade.UNAVAILABLE
    assert result.reasons == ("no evaluable provider dependencies",)


def test_replay_derivatives_without_capture_timestamp_is_unavailable_not_zero() -> None:
    """A missing capture timestamp must not become epoch 0.0 during replay."""
    packet = FeatureReplayEngine._replay_derivatives(
        {
            "selected": {
                "provider": "binance",
                "mapped_symbol": "BTCUSDT",
                "market_id": "BTCUSDT",
                "funding_rows": None,
            }
        }
    )
    assert packet["available"] is False
    assert PROVIDER_UNAVAILABLE in packet["reason"]
    assert packet["retrieved_at"] is None


def test_replay_derivatives_with_non_positive_capture_timestamp_is_unavailable() -> None:
    packet = FeatureReplayEngine._replay_derivatives(
        {"selected": {"provider": "binance", "retrieved_at": 0}}
    )
    assert packet["available"] is False
    assert PROVIDER_UNAVAILABLE in packet["reason"]
    assert packet["retrieved_at"] is None


def test_reference_price_is_never_defaulted_to_zero() -> None:
    """Missing price facts must fail closed instead of silently pricing at zero."""
    assert resolve_reference_price({}, {}) is None
    assert resolve_reference_price({"reference_price": 0}, {"last": 0}) is None
    assert resolve_reference_price({"reference_price": None}, {"last": "n/a"}) is None
    assert resolve_reference_price({"reference_price": float("nan")}, {"last": None}) is None


def test_reference_price_prefers_captured_payload_over_ticker() -> None:
    assert resolve_reference_price({"reference_price": 101.5}, {"last": 99.0}) == (
        101.5,
        "payload",
    )
    assert resolve_reference_price({}, {"last": 99.0}) == (99.0, "ticker")
    assert resolve_reference_price({"reference_price": 0}, {"last": 99.0}) == (
        99.0,
        "ticker",
    )
