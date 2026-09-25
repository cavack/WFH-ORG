"""Replay packets now carry the STRICT evaluation — PR-2's parity seam.

The doc contract (docs/STRICT_PROVIDER_INDEPENDENT_V1.md follow-up): replay
payloads carry the ``ProviderIndependenceResult`` so replay parity can
assert eligibility-outcome parity, not just row-level idempotency. The same
evaluation joins the production-vs-replay equivalence diff, so a replay may
never be EQUIVALENT while grading its own evidence differently than
production did.

RED/GREEN: written first; fails with ``KeyError: 'provider_independence'``
until the wiring exists.
"""

from __future__ import annotations

import asyncio

from test_feature_replay import _payload

from waterfallhunter.core.entry_decision import provider_independence_from_metrics
from waterfallhunter.core.feature_replay import EQUIVALENT, FeatureReplayEngine
from waterfallhunter.core.reliability_gates import check_replay_parity
from waterfallhunter.core.strict_provider_independent import (
    ProviderIndependenceResult,
)


def _candle_features_view(payload: dict) -> dict:
    details = (payload["metrics"].get("candle_analysis") or {}).get("details") or {}
    return {
        timeframe: context
        for timeframe, context in details.items()
        if isinstance(context, dict) and context.get("valid") is True
    }


def test_replay_packet_carries_evaluation_matching_production_facts() -> None:
    payload = asyncio.run(_payload())
    result = asyncio.run(FeatureReplayEngine().replay(payload))

    assert result["status"] == EQUIVALENT
    independence = result["provider_independence"]
    assert independence["policy_version"] == "STRICT_PROVIDER_INDEPENDENT_V1"

    # Parity with what the production facts imply: same inputs, same grade.
    expected = provider_independence_from_metrics(
        {
            "candle_features": _candle_features_view(payload),
            "microstructure": payload["metrics"]["microstructure"],
            "derivatives": payload["metrics"]["derivatives"],
        }
    )
    assert independence == expected


def test_replay_evaluation_is_deterministic_across_runs() -> None:
    payload = asyncio.run(_payload())
    first = asyncio.run(FeatureReplayEngine().replay(payload))
    second = asyncio.run(FeatureReplayEngine().replay(payload))

    comparison = check_replay_parity(
        candidate_id="TEST/USDT:USDT",
        original=ProviderIndependenceResult.model_validate(
            first["provider_independence"]
        ),
        replay=ProviderIndependenceResult.model_validate(
            second["provider_independence"]
        ),
    )

    assert comparison.parity is True
    assert comparison.mismatches == ()


def test_replay_with_unavailable_derivatives_degrades_not_fabricates() -> None:
    payload = asyncio.run(_payload())
    reason = "no complete live derivatives data source in exchange waterfall"
    attempted = {
        "exchange": "binance",
        "mapped_symbol": "TEST/USDT:USDT",
        "market_id": "TESTUSDT",
        "retrieved_at": None,
        "reason": "price incompatible with reference",
    }
    payload["metrics"]["derivatives"] = {
        "available": False,
        "reason": reason,
        "source_exchange": None,
        "mapped_symbol": None,
        "market_id": None,
        "retrieved_at": None,
        "fallback_attempts": [attempted],
    }
    payload["metrics"]["source_capture"]["derivatives"] = {
        "selected": None,
        "fallback_attempts": [attempted],
    }
    payload["metrics"]["score"] = None
    payload["metrics"]["score_components"] = {}
    payload["metrics"]["quality_gates"] = {"complete_fresh_derivatives_packet": False}
    payload["metrics"]["analysis_reason"] = reason
    payload["result"]["is_valid"] = False
    payload["result"]["suggested_status"] = "REJECTED"

    result = asyncio.run(FeatureReplayEngine().replay(payload))

    # Still equivalent — and the replay reports the SAME gap instead of a
    # fabricated clean grade (fail-closed, no zero-fill).
    assert result["status"] == EQUIVALENT
    independence = result["provider_independence"]
    assert independence["outcome"] == "ALERT_ELIGIBLE"
    assert independence["decision_grade"] == "RESEARCH_ONLY"
    assert independence["degraded_optional_features"] == ["coinglass_derivatives"]
    assert (
        "coinglass_derivatives: PROVIDER_UNAVAILABLE" in independence["reason_codes"]
    )
    assert "provider_independence" not in result["differences"]
