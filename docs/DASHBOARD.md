# Dashboard

The public dashboard is the WaterfallHunter **Decision Terminal**, not a research ranking page and not an order-entry surface.

Public edge: <https://waterfall.booksreadlive.online/dashboard>

For the current time-bound Production snapshot, read [Current Status](CURRENT_STATUS.md).

## Canonical snapshot contract

The frontend consumes the backend-owned `dashboard_snapshot_v2` contract (`schema_version=2.0`) through the dashboard base path:

- `GET /dashboard/api/candidates` — current canonical snapshot.
- `GET /dashboard/api/stream` — SSE stream carrying schema-valid `snapshot` and `heartbeat` events.

The snapshot contract requires `total == len(candidates)`. `decision_terminal.counts` is the authoritative aggregate across the evaluated universe. Presentation arrays such as `entry_ready`, `forming`, `active`, or `late` are bounded/curated UI groups and must not be treated as if their array length were the aggregate count.

## Primary information order

1. `ENTRY_READY` — proactive signal state, maximum three visible cards.
2. `FORMING` — developing evidence, explicitly not ready to enter, maximum six visible cards.
3. `ACTIVE` and recent canonical transitions where relevant.
4. Dominant blockers / zero-entry diagnostics.
5. Searchable, filterable, paginated all-candidates table.
6. Secondary research/validation panels loaded on demand.

A high research score, lifecycle `TRIGGERED`, or optional AI/provider observation never becomes an entry cue in the frontend.

## Decision-card evidence

Where the canonical backend packet provides it, a card may display:

- symbol, canonical decision, readiness, lifecycle context, and timestamps;
- entry zone, stop, TP levels, and advisory leverage state;
- evidence freshness/coverage;
- OI, funding, taker/flow, cascade/liquidation context;
- spread, depth/slippage, cross-exchange agreement, and execution suitability;
- Anti-Chase state and blocker/reason codes;
- optional Gemini advisory.

Unavailable evidence must be rendered as unavailable/partial according to the backend contract. The frontend must never silently convert missing provider evidence to zero, false, bullish, or bearish.

## Leverage presentation

Leverage is advisory-only. Canonical non-actionable decisions such as `LATE` and `NO_TRADE` legitimately carry `NOT_RECOMMENDED` with `leverage=null`. Numeric leverage is only meaningful when the backend leverage advisory is `AVAILABLE`; the frontend does not calculate or infer a replacement value.

## Transport state versus data freshness

`Live stream` means a valid application event has been received, not merely that a socket opened. Transport state and evidence freshness are distinct. SSE reconnect/fallback behavior must preserve the last valid schema state and fall back to polling when application events stop.

## Research separation

Replay, production-evidence recorder health, historical outcomes, lifecycle shadow, execution observations, funnel diagnostics, and Backtest Lab are secondary research surfaces. They explain or validate the system; they do not create, veto, promote, or downgrade a canonical signal.

## Failure semantics

When no signal is ready, the terminal must say so and show the dominant blockers. It must not substitute a "Top 3" observational ranking for `ENTRY_READY`, and it must not hide provider unavailability behind a neutral-looking numeric placeholder.
