from waterfallhunter.core.notifier import TelegramNotifier


def test_signal_message_uses_unavailable_marker_instead_of_none():
    message = TelegramNotifier.build_signal_message("PEPE/USDT:USDT", {"score": 88.5, "metrics": {}})
    assert "None" not in message
    assert "Score:</b> 88.50/100" in message
    assert "No live order is placed" in message


def test_signal_message_escapes_ai_reasoning_and_includes_real_context():
    message = TelegramNotifier.build_signal_message("PEPE/USDT:USDT", {
        "score": 91,
        "metrics": {
            "ai_advisory": {"ai_advice": "SHORT", "ai_confidence": 82, "ai_reasoning": "<check>"},
            "dex_context": {"chain_id": "ethereum", "liquidity_usd": 1000000},
            "onchain_context": {"large_transfer_sample_count": 2, "largest_transfer_usd": 200000},
        },
    })
    assert "&lt;check&gt;" in message
    assert "DEX: ethereum" in message
    assert "On-chain sample: 2" in message


def test_signal_message_reports_the_actual_fallback_provider():
    message = TelegramNotifier.build_signal_message("PEPE/USDT:USDT", {
        "metrics": {"ai_advisory": {"ai_provider": "ollama"}},
    })
    assert "AI advisory (ollama)" in message


def test_signal_message_surfaces_provider_independence_gap() -> None:
    # The SIGNAL_ONLY alert itself must carry the STRICT grade: the operator
    # should see "missing derivatives context" without opening the dashboard.
    message = TelegramNotifier.build_signal_message(
        "PEPE/USDT:USDT",
        {
            "score": 88.5,
            "metrics": {
                "provider_independence": {
                    "policy_version": "STRICT_PROVIDER_INDEPENDENT_V1",
                    "outcome": "ALERT_ELIGIBLE",
                    "decision_grade": "RESEARCH_ONLY",
                    "evaluated_features": ["coinglass_derivatives"],
                    "blocking_features": [],
                    "degraded_optional_features": ["coinglass_derivatives"],
                    "reasons": ["coinglass_derivatives: plan quota exceeded"],
                    "reason_codes": [
                        "coinglass_derivatives: PROVIDER_UNAVAILABLE"
                    ],
                },
            },
        },
    )

    assert "RESEARCH ONLY" in message
    assert "coinglass_derivatives" in message


def test_signal_message_stays_clean_without_a_gap() -> None:
    message = TelegramNotifier.build_signal_message(
        "PEPE/USDT:USDT",
        {
            "score": 88.5,
            "metrics": {
                "provider_independence": {
                    "policy_version": "STRICT_PROVIDER_INDEPENDENT_V1",
                    "outcome": "ALERT_ELIGIBLE",
                    "decision_grade": "DECISION_GRADE",
                    "evaluated_features": ["coinglass_derivatives"],
                    "blocking_features": [],
                    "degraded_optional_features": [],
                    "reasons": [],
                    "reason_codes": [],
                },
            },
        },
    )

    assert "Evidence:" not in message
