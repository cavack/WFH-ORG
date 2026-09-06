# WFH-ORG Migration Workspace

This directory is the provenance control plane for the clean migration from `cavack/wfh` and `cavack/wfh-dr` into `cavack/WFH-ORG`.

## Frozen source inputs

- Primary source: `cavack/wfh@3e88df0014c30a8aae656a78cc949689174a631f` — 519 tracked files.
- DR source: `cavack/wfh-dr@add3f01cf3b9f3e55d735294dae99d5a5792b5c2` — 3 tracked files.
- Fix candidate PR #127: `9b97820b43503cd0ef1d07950cbbad2ea7a79b43`.
- Fix candidate PR #128: `6db3472980c9d16fe090317324b94f743edaa955`.
- Provider/dependency evidence PR #93: `3b0a4f70620edb1159efb44c1c8aaeeb05f6a4af` (closed, unmerged).

The baseline refs are immutable inputs. Later movement of legacy `main` does not silently change this migration.

## Manifest contract

`source-manifest.json` contains one entry for every frozen tracked file, including the exact source commit, path, blob SHA, and Git mode. The initial inventory deliberately uses `UNREVIEWED` for every source file; no runtime file is admitted merely because it existed in a legacy repository.

Allowed final dispositions are `KEEP`, `FIX_FIRST`, `SUPERSEDED`, `DROP`, and `QUARANTINE`.

Inventory verification:

```bash
python3 scripts/verify_migration_manifest.py migration/source-manifest.json --allow-unreviewed
```
Strict/release verification:

```bash
python3 scripts/verify_migration_manifest.py migration/source-manifest.json
```

Strict verification must fail while any `UNREVIEWED` entry remains. At this checkpoint it fails with exactly 522 pending entries; that is intentional and prevents accidental release before file-by-file disposition is complete.

Production is not modified by Task 1. Legacy remotes are fetch-only evidence sources in the isolated migration workspace and are never merged as ancestry into the clean repository history.
