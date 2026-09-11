"""Read-only counterfactual Anti-Chase replay against recorded production decisions.

Reproduces the failure-mode statistics that motivated the sign-aware
Anti-Chase correctness fix: how many recorded ``LATE`` +
``ANTI_CHASE_HARD_BLOCK`` decisions carry a real signed below-support
extension at the policy threshold, versus how many are explained by the
historical absolute-distance measurement defect.

The measurement semantics here mirror the fixed ``_anti_chase_observation``
logic in ``waterfallhunter.core.entry_decision``: only signed
``distance_to_support_atr < 0`` can produce a post-break extension, and an
absent sign is never guessed. This script is strictly read-only
(``mode=ro`` + ``PRAGMA query_only``) and observational.

Usage::

    python scripts/anti_chase_counterfactual_replay.py \\
        --db-path /path/to/waterfall_registry.db [--start ISO --end ISO]
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import json
import sqlite3
import zlib
from dataclasses import dataclass

ENTRY_TIMEFRAMES = frozenset({"15m", "5m"})
ANTI_CHASE_THRESHOLD_ATR = 1.2
DEFAULT_PAIRING_TOLERANCE_SECONDS = 2700
DEFAULT_THRESHOLDS = (0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0)
DEFAULT_DB_PATH = "/var/lib/docker/volumes/301e9549ec50aa8d5fdd128cc156f181004d30b9_waterfall_data/_data/waterfall_registry.db"


@dataclass(frozen=True)
class SignedExtension:
    """Corrected per-timeframe measurement for one candle-features packet."""

    abs_max_atr: float
    signed_max_atr: float
    confirmed_support_break: bool
    entry_timeframe_max_atr: float
    has_below_support: bool


def measure_signed_extension(candle_features: object) -> SignedExtension | None:
    """Reduce a candle_features packet to signed Anti-Chase evidence.

    Returns ``None`` when the packet is absent or carries no usable sign on
    any timeframe (evidence is never guessed). Only signed distances strictly
    below zero contribute to ``signed_max_atr``.
    """
    if not isinstance(candle_features, dict):
        return None
    distances: list[tuple[float, bool, str]] = []  # (distance, support_broken, timeframe)
    for timeframe, packet in candle_features.items():
        if not isinstance(packet, dict):
            continue
        value = packet.get("distance_to_support_atr")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        distances.append((float(value), packet.get("support_broken") is True, str(timeframe)))
    if not distances:
        return None
    abs_max = max(abs(value) for value, _, _ in distances)
    below = [(abs(value), broken) for value, broken, _ in distances if value < 0.0]
    if not below:
        return SignedExtension(round(abs_max, 4), 0.0, False, 0.0, False)
    signed_max = max(value for value, _ in below)
    confirmed = any(broken for value, broken in below if value == signed_max and broken)
    entry_max = max(
        (
            abs(value)
            for value, _, timeframe in distances
            if value < 0.0 and timeframe in ENTRY_TIMEFRAMES
        ),
        default=0.0,
    )
    return SignedExtension(
        round(abs_max, 4),
        round(signed_max, 4),
        confirmed,
        round(entry_max, 4),
        True,
    )


def nearest_event(times_sorted: list[int], observed_at: float, tolerance: int) -> int | None:
    """Nearest recorded decision event within ``tolerance`` seconds."""
    if not times_sorted:
        return None
    index = bisect.bisect_left(times_sorted, observed_at)
    if index < len(times_sorted) and times_sorted[index] - observed_at <= tolerance:
        return times_sorted[index]
    if index > 0 and observed_at - times_sorted[index - 1] <= tolerance:
        return times_sorted[index - 1]
    return None

def load_late_event_times(
    connection: sqlite3.Connection,
    start: float,
    end: float,
    block_reason: str = "ANTI_CHASE_HARD_BLOCK",
) -> dict[str, list[int]]:
    """Collect sorted ``LATE`` decision-event timestamps per symbol."""
    times: dict[str, list[int]] = {}
    cursor = connection.execute(
        "SELECT symbol, event_at, packet_json FROM entry_decision_events "
        "WHERE decision='LATE' AND event_at>=? AND event_at<=?",
        (int(start), int(end)),
    )
    for symbol, event_at, packet_json in cursor:
        try:
            packet = json.loads(packet_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if block_reason not in set(packet.get("block_reasons") or []):
            continue
        times.setdefault(str(symbol), []).append(int(event_at))
    for values in times.values():
        values.sort()
    return times


def pair_late_events_with_snapshots(
    connection: sqlite3.Connection,
    late_event_times: dict[str, list[int]],
    start: float,
    end: float,
    tolerance_seconds: int = DEFAULT_PAIRING_TOLERANCE_SECONDS,
) -> list[tuple[str, float, SignedExtension]]:
    """Pair production-evidence snapshots with nearby LATE decision events."""
    paired: list[tuple[str, float, SignedExtension]] = []
    cursor = connection.execute(
        "SELECT symbol, observed_at, valid_candle_timeframes, evidence_zlib "
        "FROM production_evidence_snapshots WHERE observed_at>=? AND observed_at<=?",
        (start, end),
    )
    for symbol, observed_at, valid_timeframes, evidence_blob in cursor:
        if not valid_timeframes:
            continue
        event_times = late_event_times.get(str(symbol))
        if not event_times:
            continue
        if nearest_event(event_times, float(observed_at), tolerance_seconds) is None:
            continue
        try:
            payload = json.loads(zlib.decompress(evidence_blob))
        except (TypeError, zlib.error, json.JSONDecodeError):
            continue
        metrics = payload.get("metrics") if isinstance(payload, dict) else None
        measurement = measure_signed_extension((metrics or {}).get("candle_features"))
        if measurement is None:
            continue
        paired.append((str(symbol), float(observed_at), measurement))
    return paired


@dataclass(frozen=True)
class ThresholdRow:
    """One row of the threshold-response curve."""

    threshold_atr: float
    signed_count: int
    confirmed_count: int
    entry_timeframe_count: int


@dataclass(frozen=True)
class ReplayResult:
    """Aggregated counterfactual replay statistics."""

    paired_snapshots: int
    zero_below_support: int
    threshold_rows: tuple[ThresholdRow, ...]


def analyze_paired_measurements(
    measurements: list[SignedExtension],
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> ReplayResult:
    """Aggregate paired measurements into the threshold-response table."""
    rows = tuple(
        ThresholdRow(
            threshold_atr=threshold,
            signed_count=sum(1 for m in measurements if m.signed_max_atr >= threshold),
            confirmed_count=sum(
                1
                for m in measurements
                if m.confirmed_support_break and m.signed_max_atr >= threshold
            ),
            entry_timeframe_count=sum(
                1 for m in measurements if m.entry_timeframe_max_atr >= threshold
            ),
        )
        for threshold in thresholds
    )
    zero_below = sum(1 for m in measurements if not m.has_below_support)
    return ReplayResult(
        paired_snapshots=len(measurements),
        zero_below_support=zero_below,
        threshold_rows=rows,
    )


def format_replay_report(result: ReplayResult, window: str) -> str:
    """Human-readable summary suitable for research notes and PR context."""
    total = result.paired_snapshots
    if total == 0:
        return f"counterfactual anti-chase replay [{window}]: no paired snapshots"
    lines = [
        f"counterfactual anti-chase replay [{window}]",
        f"paired LATE+ANTI_CHASE_HARD_BLOCK snapshots: {total}",
        (
            "snapshots with NO below-support distance at all: "
            f"{result.zero_below_support} ({100.0 * result.zero_below_support / total:.1f}%)"
        ),
        "",
        "threshold | signed>=T | confirmed>=T | entry-tf(15m/5m)>=T",
    ]
    for row in result.threshold_rows:
        lines.append(
            f"{row.threshold_atr:8.1f} | {row.signed_count:9d} "
            f"({100.0 * row.signed_count / total:5.1f}%) | "
            f"{row.confirmed_count:6d} ({100.0 * row.confirmed_count / total:5.1f}%) | "
            f"{row.entry_timeframe_count:6d} "
            f"({100.0 * row.entry_timeframe_count / total:5.1f}%)"
        )
    return "\n".join(lines)


def run_replay(
    db_path: str,
    start: float,
    end: float,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    tolerance_seconds: int = DEFAULT_PAIRING_TOLERANCE_SECONDS,
) -> ReplayResult:
    """Read-only counterfactual replay against the production registry."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro&uri=true")
    try:
        connection.execute("PRAGMA query_only=ON")
        late_event_times = load_late_event_times(connection, start, end)
        paired = pair_late_events_with_snapshots(
            connection,
            late_event_times,
            start,
            end,
            tolerance_seconds=tolerance_seconds,
        )
    finally:
        connection.close()
    return analyze_paired_measurements([m for _, _, m in paired], thresholds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite registry path (opened read-only)")
    parser.add_argument("--start", required=False, help="window start (ISO 8601 UTC, e.g. 2026-09-08T00:00:00+00:00)")
    parser.add_argument("--end", required=False, help="window end (ISO 8601 UTC; defaults to now)")
    parser.add_argument("--tolerance", type=int, default=DEFAULT_PAIRING_TOLERANCE_SECONDS)
    args = parser.parse_args(argv)

    end = (
        datetime.datetime.fromisoformat(args.end).timestamp()
        if args.end
        else datetime.datetime.now(datetime.timezone.utc).timestamp()
    )
    start = (
        datetime.datetime.fromisoformat(args.start).timestamp()
        if args.start
        else end - 3 * 86400
    )
    window = (
        f"{datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat()} .. "
        f"{datetime.datetime.fromtimestamp(end, datetime.timezone.utc).isoformat()}"
    )
    result = run_replay(args.db_path, start, end, tolerance_seconds=args.tolerance)
    print(format_replay_report(result, window))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())