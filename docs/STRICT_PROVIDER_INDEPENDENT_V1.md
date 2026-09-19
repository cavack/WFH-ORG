# STRICT_PROVIDER_INDEPENDENT_V1

## Product framing (read this first)

WaterfallHunter / WFH-ORG is a **manual-action signal-alert system**, not a
passive research log. It continuously evaluates candidates and surfaces
alerts for a human operator to review. The operator decides and executes
manually; the system itself never places or automates order execution
(`LIVE_TRADING_ENABLED=false`).

Throughout this document and the accompanying code, **`NOT_ALERT_GRADE`
does not mean "only fit for academic study."** It means: *the evidence for
this candidate is currently incomplete or unreliable enough that it must
not be surfaced to the operator as an actionable alert.* It is a
data-quality gate on what gets shown as an alert, not a statement about the
product's purpose.

## Status

Policy module introduced on branch `feat/strict-provider-independent-v1`:
`backend/src/waterfallhunter/core/strict_provider_independent.py` plus
`backend/tests/test_strict_provider_independent.py`. Not yet wired into
production scoring or validation. Integration into
`multi_exchange_validator.py`, `scientific_validation.py`, and
`feature_replay.py` is tracked as follow-up work below.

## Problem

The STRICT signal class has historically been described as depending on
derivatives evidence (funding rate, open interest, crowding) sourced from
CoinGlass. Issue #20 records that the CoinGlass derivatives packet is
currently `UNAVAILABLE` under the active provider plan. Without an explicit
policy, this creates two unacceptable outcomes:

1. Alert eligibility could silently degrade (missing values treated as
   zero/neutral), surfacing an alert to the operator that looks complete
   but is not.
2. Alert eligibility could become permanently blocked while CoinGlass is
   unavailable, even for candidates whose mandatory (non-derivatives)
   evidence is fully observed and fresh — hiding alerts the operator
   should actually see.

Both outcomes are inconsistent with this project's SIGNAL_ONLY, fail-closed,
provenance-first design already visible in `contracts.py`,
`decision_terminal.py`, and `lifecycle_v2_shadow.py`.

## Policy

Every feature or provider a candidate depends on is classified into exactly
one requirement level:

| Requirement | Meaning |
| --- | --- |
| `MANDATORY` | The candidate cannot be `ALERT_ELIGIBLE` without this evidence being `ACTIVE`. |
| `OPTIONAL` | The candidate may remain `ALERT_ELIGIBLE` while this is `UNAVAILABLE`, but the gap must stay visible to the operator. |
| `EXCLUDED_FROM_STRICT` | Never required for alert eligibility; retained for experimental/internal cohorts only. |

CoinGlass-derived features (funding rate, open interest, crowding) are
classified `OPTIONAL` under `STRICT_PROVIDER_INDEPENDENT_V1`. This means:

- A candidate whose only gap is CoinGlass being `UNAVAILABLE` remains
  `ALERT_ELIGIBLE` and is still surfaced to the operator.
- The gap is never hidden: it is recorded in `degraded_optional_features`
  and must propagate into evidence, dashboards, and replay payloads as an
  explicit `UNAVAILABLE` / reason pair, consistent with the existing
  `DERIVATIVES_UNAVAILABLE` reason code in `decision_terminal.py`. The
  operator should be able to see "this alert is missing derivatives
  context" at a glance.
- If a future change makes a CoinGlass-derived feature `MANDATORY` for a
  specific strategy profile, that profile must accept that alert
  eligibility degrades to `NOT_ALERT_GRADE` while the provider is
  unavailable. This is a deliberate trade-off, not an accident.

## Hard rules

1. **No silent zero-fill.** An `UNAVAILABLE` feature is never treated as a
   neutral or zero value in scoring, validation, or replay. This is
   consistent with the existing `unavailable_components` tracking in
   `score_v2.py`.
2. **No unexplained absence.** Every `UNAVAILABLE` dependency must carry a
   non-empty machine-readable `reason`. The policy module raises
   `ValueError` if this is violated.
3. **Mandatory blocks, optional degrades.** Only `MANDATORY` features being
   unavailable force `NOT_ALERT_GRADE`. `OPTIONAL` and
   `EXCLUDED_FROM_STRICT` features never block alert eligibility on their
   own.
4. **Replay must reproduce the same eligibility outcome.** If a decision was
   `ALERT_ELIGIBLE` with CoinGlass `UNAVAILABLE`, replaying it must also
   report `ALERT_ELIGIBLE` with the same degraded/optional feature list and
   the same reasons — not a different outcome because the provider became
   available later. This aligns with the replay-context handling already
   present in `feature_replay.py`.
5. **SIGNAL_ONLY and manual execution are unaffected.** This policy only
   classifies evidence completeness for alert-surfacing purposes. It does
   not create, modify, or enable any order-placement or automated-execution
   path. `LIVE_TRADING_ENABLED` remains mandatory and unrelated to this
   policy; the operator continues to execute manually on any alert they
   choose to act on.

## Non-goals of this change

- This document does not remove CoinGlass integration code
  (`core/coinglass.py` is unchanged).
- This document does not change score weights, thresholds, or Anti-Chase
  behavior.
- This document does not certify any current production release as
  alert-grade end-to-end. Production status remains `DEPLOYED_UNVERIFIED`
  until the separate release-certification backlog (PR-3) is closed.
- This document does not add, modify, or enable any automated or live
  order-execution capability.

## Follow-up integration work (tracked, not yet implemented here)

- Wire `evaluate_provider_independence` into `multi_exchange_validator.py`
  wherever a `CoinGlassDerivativesClient` result is consumed, replacing any
  implicit "missing means excluded" behavior with an explicit
  `FeatureDependency`.
- Extend `ScientificValidationPolicy` in `scientific_validation.py` so a
  cohort whose CoinGlass dependency is `UNAVAILABLE` is still eligible for
  validated review, while a cohort with a `MANDATORY` gap is not.
- Extend replay payloads in `feature_replay.py` to carry the
  `ProviderIndependenceResult` alongside the existing
  `replay_unavailable_reason` handling, so replay parity checks (PR-2) can
  assert eligibility-outcome parity, not just row-level idempotency.
- Surface `degraded_optional_features` and `blocking_features` on the
  operator-facing dashboard (PR-4) so the reason an alert is `ALERT_ELIGIBLE`
  with a gap, or `NOT_ALERT_GRADE`, is always visible next to the alert.
