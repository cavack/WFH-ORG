"""Aggregate reliability gates: freshness SLO and replay parity.

WaterfallHunter / WFH-ORG already enforces per-candidate freshness at
decision time (see ``entry_decision.py``: ``max_analysis_age_seconds=180.0``,
``max_reference_age_seconds=60.0``). This module adds two things that did
not previously exist as first-class, testable checks:

1. An aggregate freshness SLO over a *window* of evaluations (p50/p95/max),
   so a release can be judged on sustained behavior under load, not just a
   single candidate's instantaneous freshness. This mirrors the documented
   target ("global usable analysis p95 < 180s") that was previously only
   checked manually during soak windows.
2. A replay-parity comparator that reuses
   :mod:`waterfallhunter.core.strict_provider_independent` (PR-1) to assert
   that replaying a decision's inputs produces the *same* alert-eligibility
   outcome as the original decision — not just an idempotent database row.

Both gates are pure, deterministic, and have no I/O. They do not fetch
data, touch the database, or call any provider. They do not create,
modify, or enable any order-placement or automated-execution path;
LIVE_TRADING_ENABLED and SIGNAL_ONLY are unrelated to and unaffected by
this module.
"""

from __future__ import annotations

import statistics
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from waterfallhunter.core.strict_provider_independent import (
    EligibilityOutcome,
    ProviderIndependenceResult,
)

DEFAULT_MAX_ANALYSIS_AGE_SECONDS = 180.0
"""Mirrors entry_decision.EntryDecisionPolicy.max_analysis_age_seconds."""


class FreshnessSample(BaseModel):
    """One observed analysis-age measurement within an evaluation window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    analysis_age_seconds: float = Field(ge=0.0)


class FreshnessSLOResult(BaseModel):
    """Windowed freshness SLO evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_count: int
    p50_seconds: float
    p95_seconds: float
    max_seconds: float
    threshold_seconds: float
    slo_pass: bool
    breaching_candidate_ids: tuple[str, ...] = Field(default_factory=tuple)


def compute_freshness_slo(
    samples: Sequence[FreshnessSample],
    *,
    threshold_seconds: float = DEFAULT_MAX_ANALYSIS_AGE_SECONDS,
) -> FreshnessSLOResult:
    """Compute p50/p95/max analysis age over a window and check the SLO.

    Parameters
    ----------
    samples:
        Non-empty sequence of :class:`FreshnessSample`. Each sample is one
        candidate's observed ``analysis_age_seconds`` at evaluation time.
    threshold_seconds:
        The SLO target for p95 analysis age. Defaults to the project's
        existing per-candidate freshness contract (180.0 seconds).

    Returns
    -------
    FreshnessSLOResult
        ``slo_pass`` is True only if ``p95_seconds <= threshold_seconds``.
        ``breaching_candidate_ids`` lists every sample whose individual age
        exceeds the threshold, regardless of overall p95 pass/fail, so a
        release reviewer can see exactly which candidates were stale.

    Raises
    ------
    ValueError
        If ``samples`` is empty. An SLO cannot be evaluated over zero
        observations; callers must not silently treat "no data" as "pass".
    """

    if not samples:
        raise ValueError(
            "cannot compute a freshness SLO over an empty sample window; "
            "absence of data must not be treated as a passing SLO"
        )

    ages = [sample.analysis_age_seconds for sample in samples]
    ages_sorted = sorted(ages)

    p50 = statistics.median(ages_sorted)
    if len(ages_sorted) == 1:
        p95 = ages_sorted[0]
    else:
        quantiles = statistics.quantiles(ages_sorted, n=100, method="inclusive")
        p95 = quantiles[94]
    maximum = max(ages_sorted)

    breaching = tuple(
        sorted(
            sample.candidate_id
            for sample in samples
            if sample.analysis_age_seconds > threshold_seconds
        )
    )

    return FreshnessSLOResult(
        sample_count=len(samples),
        p50_seconds=p50,
        p95_seconds=p95,
        max_seconds=maximum,
        threshold_seconds=threshold_seconds,
        slo_pass=p95 <= threshold_seconds,
        breaching_candidate_ids=breaching,
    )


class ReplayComparison(BaseModel):
    """Result of comparing an original decision's eligibility to its replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    parity: bool
    mismatches: tuple[str, ...] = Field(default_factory=tuple)


def check_replay_parity(
    *,
    candidate_id: str,
    original: ProviderIndependenceResult,
    replay: ProviderIndependenceResult,
) -> ReplayComparison:
    """Assert that a replayed decision reproduces the original's eligibility.

    Compares ``outcome``, ``blocking_features``, and
    ``degraded_optional_features`` between the original
    :class:`ProviderIndependenceResult` (from PR-1's
    ``evaluate_provider_independence``) and a replay of the same inputs.
    Row-level idempotency (e.g. a stable ``snapshot_id``) is not sufficient
    on its own: this checks that the *decision itself* is reproducible, not
    merely that storing it twice produces the same row.

    Parameters
    ----------
    candidate_id:
        Identifier for the candidate/signal being compared, used only for
        reporting.
    original:
        The eligibility result recorded at the time of the original
        decision.
    replay:
        The eligibility result produced by replaying the same inputs.

    Returns
    -------
    ReplayComparison
        ``parity`` is True only if outcome, blocking features, and
        degraded optional features are all identical. ``mismatches``
        lists every field that differs, so a reviewer can see exactly what
        diverged.
    """

    mismatches: list[str] = []

    if original.outcome is not replay.outcome:
        mismatches.append(
            f"outcome: original={original.outcome.value} replay={replay.outcome.value}"
        )
    if original.blocking_features != replay.blocking_features:
        mismatches.append(
            "blocking_features: original="
            f"{original.blocking_features} replay={replay.blocking_features}"
        )
    if original.degraded_optional_features != replay.degraded_optional_features:
        mismatches.append(
            "degraded_optional_features: original="
            f"{original.degraded_optional_features} replay={replay.degraded_optional_features}"
        )

    return ReplayComparison(
        candidate_id=candidate_id,
        parity=not mismatches,
        mismatches=tuple(mismatches),
    )


class ReleaseReadiness(BaseModel):
    """Combined verdict from the freshness SLO and replay-parity gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ready: bool
    freshness: FreshnessSLOResult
    replay_mismatches: tuple[ReplayComparison, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)


def evaluate_release_readiness(
    *,
    freshness: FreshnessSLOResult,
    replay_comparisons: Sequence[ReplayComparison],
) -> ReleaseReadiness:
    """Combine the freshness SLO and replay-parity gates into one verdict.

    A release is ``ready`` only if the freshness SLO passes AND every
    replay comparison shows parity. This function does not evaluate
    anything about CoinGlass or STRICT_PROVIDER_INDEPENDENT_V1 directly;
    it consumes whatever :class:`ProviderIndependenceResult` values the
    caller already computed for each candidate, keeping this module
    focused on reliability (freshness, determinism), not evidence
    completeness.
    """

    reasons: list[str] = []

    if not freshness.slo_pass:
        reasons.append(
            f"freshness SLO breached: p95={freshness.p95_seconds:.1f}s "
            f"> threshold={freshness.threshold_seconds:.1f}s"
        )

    failing_replays = tuple(
        comparison for comparison in replay_comparisons if not comparison.parity
    )
    if failing_replays:
        reasons.append(
            f"{len(failing_replays)} candidate(s) failed replay parity: "
            f"{', '.join(c.candidate_id for c in failing_replays)}"
        )

    return ReleaseReadiness(
        ready=freshness.slo_pass and not failing_replays,
        freshness=freshness,
        replay_mismatches=failing_replays,
        reasons=tuple(reasons),
    )
