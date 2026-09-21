# RELIABILITY_ALERT_GRADE_GATES_V1

## Status

Introduced on branch `feat/reliability-alert-grade-gates`:
`backend/src/waterfallhunter/core/reliability_gates.py` plus
`backend/tests/test_reliability_gates.py`. Not yet wired into the release
pipeline, CI, or the production dashboard. Wiring is tracked as follow-up
work below.

## Relationship to existing freshness contract

WFH-ORG already enforces per-candidate freshness at decision time:
`entry_decision.py` defines `max_analysis_age_seconds=180.0` and
`max_reference_age_seconds=60.0`, and every candidate carries
`analysis_age_seconds` / `reference_age_seconds` in its evidence
(`contracts.py`). This module does not replace that per-candidate check.

What was missing was an **aggregate, windowed** view: the documented target
"global usable analysis p95 < 180s" had previously only been checked
manually during ad hoc soak windows (see the Wave A specification that
recorded a p95 of approximately 568 seconds against this same 180s target).
`compute_freshness_slo()` makes that check a reusable, testable function
over any window of `FreshnessSample` observations.

## Relationship to PR-1 (STRICT_PROVIDER_INDEPENDENT_V1)

`check_replay_parity()` consumes
`waterfallhunter.core.strict_provider_independent.ProviderIndependenceResult`
directly. It asserts that replaying a candidate's inputs produces the same
`EligibilityOutcome`, the same `blocking_features`, and the same
`degraded_optional_features` as the original decision. This is stricter
than row-level idempotency (e.g. a stable `snapshot_id` in the existing
feature-replay store): it checks that the *decision logic* is reproducible
for the same inputs, not merely that storing the same row twice is a no-op.

## What "release-ready" means here

`evaluate_release_readiness()` combines both gates:

- `ready = True` only if the freshness SLO passes (`p95 <= threshold`) AND
  every supplied replay comparison shows parity.
- Any breach produces an explicit, human-readable reason in `reasons`, and
  breaching candidates are listed by ID in `breaching_candidate_ids` /
  `replay_mismatches` so a reviewer can see exactly what failed and for
  which candidate — not just an aggregate pass/fail flag.

This verdict is about **reliability** (is the pipeline fast and
deterministic enough to trust its output), not about **evidence
completeness** (whether a specific candidate has enough data to be
alert-eligible, which is PR-1's concern) or about **release/DR
certification** (whether the deployed artifact itself has been
restore-tested, which is a separate PR-3 concern).

## Hard rules

1. **No SLO on empty data.** `compute_freshness_slo()` raises `ValueError`
   on an empty sample window. Absence of observations must never be
   silently treated as a passing SLO.
2. **p95, not average.** The gate is deliberately based on the 95th
   percentile of analysis age, matching the project's own stated target,
   because an average can hide a long tail of stale candidates that an
   operator would still see as delayed alerts.
3. **Replay parity checks the decision, not just the row.** A `parity=True`
   result requires outcome, blocking features, and degraded optional
   features to all match exactly between the original and the replay.
4. **This module has no side effects.** It performs no I/O, database
   access, or provider calls. It cannot create, modify, or enable any
   order-placement or automated-execution path. `LIVE_TRADING_ENABLED` and
   SIGNAL_ONLY are unrelated to and unaffected by this module.

## Non-goals of this change

- This document does not change any decision-terminal reason code, score
  weight, or Anti-Chase threshold.
- This document does not certify the current production release. Release
  status remains `DEPLOYED_UNVERIFIED` until the separate release/DR
  certification backlog (PR-3) closes Issue #19 and related soak/restore
  evidence.
- This document does not modify CI workflows, deployment scripts, or any
  production configuration.
- This document does not add, modify, or enable any live-trading or
  automated order-execution capability.

## Follow-up integration work (tracked, not yet implemented here)

- Feed real per-candidate `analysis_age_seconds` values (already emitted by
  `dashboard_projection.py` / `contracts.py`) into `FreshnessSample` on a
  rolling window, and expose `compute_freshness_slo()`'s result as a
  Prometheus/Grafana metric alongside existing health endpoints.
- Generate `ProviderIndependenceResult` pairs (original vs. replay) from
  `feature_replay.py`'s existing replay-context handling, and run
  `check_replay_parity()` over historical STRICT candidates as a CI
  regression check.
- Make `evaluate_release_readiness()` a required, non-bypassable gate in
  the deployment workflow (`deploy-production.yml`) once real data feeds
  are wired, so a release cannot be dispatched while `ready=False`.
