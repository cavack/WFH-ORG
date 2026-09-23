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
`backend/tests/test_strict_provider_independent.py`.

Hardened on branch `fix/reliability-hardening-20260923` (operator-facing
grading plus fail-closed replay facts, covered by
`backend/tests/test_provider_unavailable_fail_closed.py`):

- Every result now carries an explicit `decision_grade`:
  `DECISION_GRADE` only when **every** evaluated dependency was observed;
  `RESEARCH_ONLY` whenever any dependency is `UNAVAILABLE` (mandatory or
  optional); `UNAVAILABLE` when nothing was evaluated at all.
- Every unavailable dependency reports a machine-readable
  `reason_code`, defaulting to `PROVIDER_UNAVAILABLE` so a caller cannot
  omit it and let the gap disappear from the operator's view.
- `evaluate_provider_independence({})` now fails closed
  (`NOT_ALERT_GRADE` / `UNAVAILABLE`) instead of reporting a clean
  `ALERT_ELIGIBLE` result for an empty evidence set.
- `feature_replay.py` no longer fabricates facts: a derivatives capture
  with no usable `retrieved_at` is reported as `UNAVAILABLE` with reason
  `PROVIDER_UNAVAILABLE` (previously epoch `0.0`), and a replay that cannot
  resolve a positive reference price from captured data returns
  `NOT_REPLAYABLE` / `REFERENCE_PRICE_UNAVAILABLE` (previously `0.0`).

**Wired on `fix/reliability-hardening-20260923`** — report-only: the
wiring attaches the explicit evaluation but never changes a scoring,
gate, or terminal verdict by itself.

- `entry_decision.build_entry_decision` attaches `provider_independence`
  (outcome, `decision_grade`, evaluated/blocking/degraded features, human
  reasons, machine reason codes) to every user-facing packet via
  `provider_independence_from_metrics`; terminal transitions
  (EXPIRED/INVALIDATED) carry the evaluation forward.
- `multi_exchange_validator.cross_check_symbol` attaches the same
  evaluation — one shared function, so stored candidate metrics and the
  decision packet cannot disagree — right after candle, microstructure,
  and derivatives facts are assembled.
- `scientific_validation.validate_strict_scientific_evidence` accepts
  declared `provider_dependencies`: a cohort whose only gap is OPTIONAL
  (CoinGlass, Issue #20) stays eligible for validated review with the gap
  recorded on the report; a MANDATORY gap — or an empty declared map —
  fails review closed with
  `PROVIDER_EVIDENCE_MANDATORY_FEATURE_UNAVAILABLE`. Callers that declare
  nothing keep the pre-existing report shape byte-for-byte.

Still **not** done: enforcement at alert-emission time, explicit
dependency coverage for the derived scoring components (order_flow,
cross_exchange, price_location, cascade), and the eligibility side of
`feature_replay.py` payloads — all tracked as follow-up work below.

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
6. **Facts are never fabricated to look complete.** If a captured fact needed
   to re-derive a decision (the reference price, or the capture timestamp that
   ages derivatives evidence) is missing, replay reports the gap and stops
   instead of substituting `0.0`. Zero is a real market value; it must never
   mean "we did not capture this".

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

- ~~Wire `evaluate_provider_independence` into `multi_exchange_validator.py`~~
  **Done** on `fix/reliability-hardening-20260923`: `cross_check_symbol`
  attaches `provider_independence` (via the shared
  `entry_decision.provider_independence_from_metrics`) to candidate metrics.
- ~~Extend `ScientificValidationPolicy` in `scientific_validation.py`~~
  **Done** on `fix/reliability-hardening-20260923`, as an optional
  `provider_dependencies` argument on `validate_strict_scientific_evidence`
  rather than a policy field — policy fields are hash-bound, and the gate
  belongs to the cohort's evidence, not to the frozen policy. OPTIONAL gap →
  still eligible for validated review (recorded); MANDATORY gap or empty
  declared map → fails closed with
  `PROVIDER_EVIDENCE_MANDATORY_FEATURE_UNAVAILABLE`.
- Declare `provider_dependencies` at every real caller of
  `validate_strict_scientific_evidence` (CLI, review pipeline) so the gate
  is exercised in production rather than only where declared.
- ~~Surface the decision grade on advisory/dashboard~~ **Done** on
  `fix/reliability-hardening-20260923`: the SIGNAL_ONLY signal alert and
  the ENTRY READY notification render an `⚠️ Evidence: <grade> ·
  missing: …` line whenever the grade is not `DECISION_GRADE`, and both
  dashboard projections (`dashboard.compact_metrics`,
  `dashboard_projection.project_dashboard_candidate`) carry
  `provider_independence` end-to-end (`dashboard_stream` already passes
  nested decision dicts through untouched). Packets without the evaluation
  project byte-identically — no fabricated fields on legacy rows.
- Enforcement: stop *presenting* `UNAVAILABLE`/`NOT_ALERT_GRADE` results as
  alert-grade (suppress or hard-mark the signal itself) — visibility has
  landed, suppression is still open (ADV/UI findings).
- Represent the derived scoring components (order_flow, cross_exchange,
  price_location, cascade) as explicit `FeatureDependency` entries in
  `provider_independence_from_metrics`, so coverage loss shows up in
  `blocking_features`/`degraded_optional_features` instead of only in
  `reason_codes` and `evidence_coverage_pct`.
- ~~Extend replay payloads in `feature_replay.py` to carry the
  `ProviderIndependenceResult`~~ **Done** on
  `fix/reliability-hardening-20260923`: EQUIVALENT/MISMATCH packets carry
  `provider_independence`, and the same evaluation joins the
  production-vs-replay equivalence diff — both sides go through the shared
  `provider_independence_from_metrics`, so a replay can never be
  EQUIVALENT while grading its evidence differently than production did.
  NOT_REPLAYABLE packets stay unchanged (no facts, no invented grade). The
  results table keeps its fixed columns: the evaluation lands in
  `differences_json` whenever it diverges and is deterministically
  re-derivable from the snapshot otherwise; persisting it on every row
  would need a migration and is tracked separately.
- Surface `degraded_optional_features` and `blocking_features` on the
  operator-facing dashboard (PR-4) so the reason an alert is `ALERT_ELIGIBLE`
  with a gap, or `NOT_ALERT_GRADE`, is always visible next to the alert.
