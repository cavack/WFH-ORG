# RELEASE_DR_SECURITY_CERTIFICATION_V1

## Purpose

This is a fail-closed contract for certifying one exact artifact. It evaluates
real evidence supplied by CI, deployment, DR, and monitoring systems. It does
not deploy, restore, access secrets, or enable any live/automated execution.

## Required facts

A release is `CERTIFIED` only when all facts are true:

- exact non-empty Git SHA and backend/frontend image identities;
- schema verification after migration;
- restore drill and rollback rehearsal passed;
- post-deploy soak passed with zero OOM/unexpected restarts;
- deterministic security gate passed;
- SIGNAL_ONLY verified and `LIVE_TRADING_ENABLED=false`.

Any failed or missing fact is `NOT_CERTIFIED` with a stable reason code.

## Real wiring still required

The policy module is not a claim that production is currently certified.
Before it can gate a production release, `deploy-production.yml`,
`verify_production_cutover.py`, restore/rollback workflows, and monitoring
must emit real evidence for the exact Git SHA/image digests. The existing
schema-10 DR/soak debt and unsupported agentic security check remain blockers
until real restore, soak, and deterministic security artifacts pass.

## Non-goals

- No deployment, rollback, restore, secret access, or production mutation.
- No scoring/threshold/alert logic change.
- No live trading or automated order execution. SIGNAL_ONLY remains required.
