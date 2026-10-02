"""STRICT_PROVIDER_INDEPENDENT_V1 wired into the user-facing entry decision.

The entry-decision packet now carries an explicit ``provider_independence``
evaluation so the dashboard/advisory can show the decision grade and the
exact gap behind it. The wiring is report-only: it never changes scoring,
gates, or the terminal decision — the eligibility outcome and grade are
derived from the same evidence facts scoring already consumes.

RED/GREEN discipline: these tests were written first and fail with
``KeyError: 'provider_independence'`` until the wiring exists.
"""

from __future__ import annotations

from test_entry_decision import decide, strong_metrics

from waterfallhunter.core.entry_decision import build_invalidated_entry_decision


def test_strong_fresh_setup_is_decision_grade() -> None:
    packet = decide(strong_metrics())
    independence = packet["provider_independence"]

    assert independence["policy_version"] == "STRICT_PROVIDER_INDEPENDENT_V1"
    assert independence["outcome"] == "ALERT_ELIGIBLE"
    assert independence["decision_grade"] == "DECISION_GRADE"
    assert independence["evaluated_features"] == [
        "coinglass_derivatives",
        "execution",
        "microstructure",
        "structure",
        "timing",
    ]
    assert independence["blocking_features"] == []
    assert independence["degraded_optional_features"] == []
    assert independence["reasons"] == []
    assert independence["reason_codes"] == []


def test_optional_derivatives_gap_stays_alert_eligible_research_only() -> None:
    metrics = strong_metrics()
    metrics["derivatives"] = {"available": False, "reason": "CoinGlass plan quota"}
    packet = decide(metrics)
    independence = packet["provider_independence"]

    # OPTIONAL gap: eligibility holds, grade drops, gap stays visible.
    assert independence["outcome"] == "ALERT_ELIGIBLE"
    assert independence["decision_grade"] == "RESEARCH_ONLY"
    assert independence["degraded_optional_features"] == ["coinglass_derivatives"]
    assert independence["blocking_features"] == []
    assert any(
        reason.startswith("coinglass_derivatives: ")
        for reason in independence["reasons"]
    )
    assert (
        "coinglass_derivatives: PROVIDER_UNAVAILABLE" in independence["reason_codes"]
    )
    # The gap must never leak into hard blocking: OPTIONAL never blocks.
    assert "DERIVATIVES_UNAVAILABLE" not in packet["block_reasons"]
    assert packet["hard_blocked"] is False


def test_missing_derivatives_packet_is_explicitly_degraded_not_clean() -> None:
    metrics = strong_metrics()
    metrics.pop("derivatives", None)
    packet = decide(metrics)
    independence = packet["provider_independence"]

    # Missing evidence is reported as a gap — never silently clean.
    assert independence["outcome"] == "ALERT_ELIGIBLE"
    assert independence["decision_grade"] == "RESEARCH_ONLY"
    assert independence["degraded_optional_features"] == ["coinglass_derivatives"]


def test_missing_structure_evidence_is_not_alert_grade() -> None:
    metrics = strong_metrics()
    metrics["candle_features"]["4h"] = {"valid": False}
    packet = decide(metrics)
    independence = packet["provider_independence"]

    assert independence["outcome"] == "NOT_ALERT_GRADE"
    assert independence["decision_grade"] == "RESEARCH_ONLY"
    assert independence["blocking_features"] == ["structure"]
    assert "structure: STRUCTURE_UNAVAILABLE" in independence["reason_codes"]
    # The same gap was already visible to scoring before this wiring.
    assert "STRUCTURE_UNAVAILABLE" in packet["reason_codes"]


def test_invalidated_terminal_transition_retains_independence_evaluation() -> None:
    previous = decide(strong_metrics())
    packet = build_invalidated_entry_decision(
        previous,
        evaluated_at=previous["evaluated_at"],
        block_reason="STRUCTURE_INVALIDATED",
    )

    assert packet is not None
    assert packet["decision"] == "INVALIDATED"
    assert packet["provider_independence"] == previous["provider_independence"]
