# WaterfallHunter Current Status

Snapshot time: **2026-09-09 09:09 UTC**  
Canonical repository: `cavack/WFH-ORG`  
Production application revision: `e06d874797d936dd134655b606aab5f22ea221ac`

This document is the durable return point for the finalization checkpoint. It records what was directly established, what remains deferred, and which GitHub issues own the remaining work. It is not a profitability claim and it does not upgrade release certification beyond the evidence available.

## Release state

`DEPLOYED_UNVERIFIED`

`PRODUCTION_VERIFIED` is **not** claimed because the post-deploy risk-proportional soak was deferred and the current-state schema-10 canonical DR certificate has not yet been completed. See [#19](https://github.com/cavack/WFH-ORG/issues/19).

## Verified runtime facts

- `VERIFIED_FACT`: official Production deploy workflow run `34305651980` completed successfully for revision `e06d874797d936dd134655b606aab5f22ea221ac`.
- `VERIFIED_FACT`: Production checkout and running backend image/revision matched that exact application SHA during finalization checks.
- `VERIFIED_FACT`: managed SQLite is at schema `10`, `PRAGMA quick_check=ok`, and foreign-key violations were `0`.
- `VERIFIED_FACT`: public `/dashboard` and `/dashboard/api/health` returned HTTP `200`; the backend reported `healthy` and hunter progress remained fresh in the observed checks.
- `VERIFIED_FACT`: backend, frontend, watchdog, Prometheus, and Grafana were running/healthy; backend restart count was `0` and `OOMKilled=false` in the finalization checks.
- `VERIFIED_FACT`: `LIVE_TRADING_ENABLED=false` remained effective.
- `VERIFIED_FACT`: the final memory point observed before handoff was approximately `1.542 GiB / 2 GiB` for the backend. A single point is not proof of a leak or of a plateau; soak evidence remains deferred.

## Decision and leverage snapshot

The finalization dashboard snapshot contained `173` candidates:

| Canonical decision | Count |
| --- | ---: |
| `ENTRY_READY` | 0 |
| `FORMING` | 0 |
| `ACTIVE` | 0 |
| `LATE` | 108 |
| `NO_TRADE` | 65 |
| `INVALIDATED` | 0 |
| `EXPIRED` | 0 |
| `UNAVAILABLE` | 0 |

All 173 observed leverage advisories were `NOT_RECOMMENDED` with no numeric leverage, which is correct for those non-actionable decisions. No real `ENTRY_READY`/`ACTIVE` sample was present to provide a Production observation of numeric adaptive leverage. Follow-up is tracked in [#22](https://github.com/cavack/WFH-ORG/issues/22).

Protected calibration remains unchanged unless separately scientifically validated:

- `ENTRY_READY >= 78`
- `FORMING >= 55`
- Anti-Chase `1.2 ATR`

## Integration status

### Backtest Lab

- `VERIFIED_FACT`: a host-owned `BACKTEST_ARTIFACT_HMAC_KEY` is configured without committing the secret.
- `VERIFIED_FACT`: `/api/backtest-lab/contract` reported `production_bundle_available=true`, `database_writes=false`, and `promotion_allowed=false`.
- `VERIFIED_FACT`: a signed Production bundle was generated from `lbank_signal_ledger` and authenticated replay returned HTTP `200`.
- Boundary remains `SIGNAL_ONLY`; Backtest Lab cannot promote strategy or place orders.

### Gemini

- `VERIFIED_FACT`: `GEMINI_API_KEY` is present and the configured model is `gemini-flash-lite-latest`.
- `VERIFIED_FACT`: DNS, TLS, model metadata, and a direct `generateContent` provider probe succeeded; the probe response arrived in about `0.468s`, inside the canonical outer advisory timeout.
- Gemini remains advisory-only. No live canonical advisory was observed in the final snapshot because no `FORMING`/`ENTRY_READY` decision was present during that observation window.

### CoinGlass

- `VERIFIED_FACT`: the API key is present and canonical mapping resolved Binance `BTC/USDT:USDT` to market id `BTCUSDT` during diagnosis.
- `VERIFIED_FACT`: funding, OI, taker, and top-account endpoints returned CoinGlass API code `401` with message `Upgrade plan` at the tested intervals.
- Therefore CoinGlass optional derivatives evidence is currently `UNAVAILABLE`, not directional evidence. Follow-up: [#20](https://github.com/cavack/WFH-ORG/issues/20).

### Telegram

- `VERIFIED_FACT`: bot token and chat identity passed read-only `getMe`/`getChat` checks.
- `VERIFIED_FACT`: `TELEGRAM_SIGNAL_DELIVERY_ENABLED=false`; no cutover timestamp is configured; no test message was sent during finalization.
- Delivery remains intentionally deferred. Follow-up: [#21](https://github.com/cavack/WFH-ORG/issues/21).

## Deferred work / known problems

1. [#19 — Release certification debt: post-deploy soak and schema-10 canonical DR certification remain pending](https://github.com/cavack/WFH-ORG/issues/19)
2. [#20 — Provider debt: CoinGlass derivatives packet is unavailable under the current API plan](https://github.com/cavack/WFH-ORG/issues/20)
3. [#21 — Operations debt: Telegram signal delivery cutover is intentionally disabled](https://github.com/cavack/WFH-ORG/issues/21)
4. [#22 — Research follow-up: explain zero actionable signal yield without loosening protected calibration](https://github.com/cavack/WFH-ORG/issues/22)
5. [#24 — CI tooling debt: GitHub agentic security check fails because the requested Copilot model is unsupported](https://github.com/cavack/WFH-ORG/issues/24)
6. [#26 — Analysis debt: reconcile SonarCloud main-branch new-code baseline reporting 358 issues](https://github.com/cavack/WFH-ORG/issues/26)

At this snapshot there were also 10 open Dependabot maintenance PRs. They are maintenance backlog, not evidence that the deployed application is currently broken.

## Finalization CI note

- `VERIFIED_FACT`: PR #23 passed all five required branch-protection checks (`backend`, `frontend`, `container-validation`, `dependency-audit`, `repository-hygiene`), plus SonarCloud and CodeQL.
- `VERIFIED_FACT`: the separate optional `github-advanced-security` agentic job failed before producing a repository finding because its GitHub/Copilot runtime requested an unsupported model. This is tracked as CI tooling `DEBT` in [#24](https://github.com/cavack/WFH-ORG/issues/24), not as a WaterfallHunter product security defect.
- `VERIFIED_FACT`: after merge, SonarCloud's `main` Quality Gate passed but its branch summary reported `358 New issues` while the exact PR #25 analysis reported `0 New issues`. This discrepancy is tracked as analysis `DEBT` in [#26](https://github.com/cavack/WFH-ORG/issues/26); it is not being attributed to the documentation-only finalization change without baseline reconciliation.

## Historical incident records

Historical P0 diagnoses remain under `docs/engineering/`. They are preserved as lineage and design evidence, but they must not be treated as current Production facts without revalidation. In particular, post-fix memory stability still requires the deferred soak in #19 before release certification can advance.

## Resume order

When work resumes:

1. start from this file and current GitHub `main`;
2. reconcile issues #19–#22 against fresh runtime/provider evidence;
3. complete #19 before any `PRODUCTION_VERIFIED` or `CANONICAL_DR_CERTIFIED` claim;
4. keep missing optional market evidence as `UNAVAILABLE`;
5. preserve ScoreV2/lifecycle/eligibility/Anti-Chase/provenance/persistence-before-notification/scientific-validation boundaries;
6. keep `LIVE_TRADING_ENABLED=false` and do not introduce live order placement.

## Documentation/runtime distinction

GitHub `main` may advance after the Production application revision because documentation-only finalization commits do not deploy the application. Always compare the current repository SHA with the runtime revision before making a release claim.
