from __future__ import annotations

import json
import sqlite3
import zlib

from scripts.anti_chase_counterfactual_replay import (
    ANTI_CHASE_THRESHOLD_ATR,
    measure_signed_extension,
    nearest_event,
    run_replay,
)


def _features(pairs: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        timeframe: {
            "distance_to_support_atr": value,
            "support_broken": broken,
        }
        for timeframe, (value, broken) in pairs.items()
    }


def test_above_support_distance_is_not_post_break_chase():
    """VET reproduction: +3.2188 ATR above support must not be anti-chase."""
    features = _features(
        {
            "4h": (3.2188, False),
            "1h": (-0.0135, False),
            "15m": (0.764, False),
            "5m": (0.0, False),
        }
    )

    measurement = measure_signed_extension(features)

    assert measurement is not None
    assert measurement.abs_max_atr == 3.2188  # the historical (defective) signal
    assert measurement.signed_max_atr == 0.0135  # the corrected signal: tiny, far below 1.2
    assert measurement.has_below_support is True
    assert measurement.confirmed_support_break is False
    assert measurement.signed_max_atr < ANTI_CHASE_THRESHOLD_ATR


def test_below_support_distance_is_the_only_post_break_chase():
    features = _features(
        {
            "4h": (-1.35, True),
            "1h": (-0.9, False),
            "15m": (-0.4, True),
            "5m": (0.2, False),
        }
    )

    measurement = measure_signed_extension(features)

    assert measurement is not None
    assert measurement.signed_max_atr == 1.35
    assert measurement.confirmed_support_break is True
    assert measurement.entry_timeframe_max_atr == 0.4
    assert measurement.has_below_support is True
    assert measurement.signed_max_atr >= ANTI_CHASE_THRESHOLD_ATR


def test_measurement_requires_evidence_and_never_guesses_sign():
    assert measure_signed_extension(None) is None
    assert measure_signed_extension({}) is None
    assert measure_signed_extension({"4h": {"distance_to_support_atr": None}}) is None
    assert measure_signed_extension({"4h": {"distance_to_support_atr": "3.0"}}) is None
    assert measure_signed_extension({"4h": {"other": 1.0}}) is None


def test_nearest_event_matches_within_tolerance():
    times = [1000, 2000, 3000]

    assert nearest_event(times, 1000, 100) == 1000
    assert nearest_event(times, 1050, 100) == 1000
    assert nearest_event(times, 1950, 100) == 2000
    assert nearest_event(times, 2950, 100) == 3000
    assert nearest_event(times, 2900, 50) is None
    assert nearest_event([], 1000, 100) is None


def _write_registry(path: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE entry_decision_events ("
            "symbol TEXT, event_at INTEGER, decision TEXT, packet_json TEXT)"
        )
        connection.execute(
            "CREATE TABLE production_evidence_snapshots ("
            "symbol TEXT, observed_at REAL, valid_candle_timeframes TEXT, "
            "evidence_zlib BLOB)"
        )
        late_packet = json.dumps({"block_reasons": ["ANTI_CHASE_HARD_BLOCK"]})
        connection.execute(
            "INSERT INTO entry_decision_events VALUES (?, ?, ?, ?)",
            ("VETUSDT", 1757330400, "LATE", late_packet),
        )
        evidence = {
            "metrics": {
                "candle_features": _features(
                    {
                        "4h": (3.2188, False),
                        "1h": (0.5, False),
                        "15m": (0.1, False),
                    }
                )
            }
        }
        connection.execute(
            "INSERT INTO production_evidence_snapshots VALUES (?, ?, ?, ?)",
            ("VETUSDT", 1757330000.0, "4h,1h,15m", zlib.compress(json.dumps(evidence).encode())),
        )
        # Non-matching symbol snapshot must be ignored.
        connection.execute(
            "INSERT INTO production_evidence_snapshots VALUES (?, ?, ?, ?)",
            ("ALGOUSDT", 1757330000.0, "4h", zlib.compress(b"{}")),
        )
        connection.commit()
    finally:
        connection.close()


def test_run_replay_pairs_snapshots_without_production_db(tmp_path):
    db_path = str(tmp_path / "registry.db")
    _write_registry(db_path)

    result = run_replay(
        db_path,
        start=1757320000.0,
        end=1757340000.0,
        tolerance_seconds=2700,
    )

    assert result.paired_snapshots == 1
    assert result.zero_below_support == 1
    row_12 = next(r for r in result.threshold_rows if r.threshold_atr == 1.2)
    assert row_12.signed_count == 0  # the defect would have blocked with abs=3.2188
    assert row_12.confirmed_count == 0
