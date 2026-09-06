#!/usr/bin/env python3
"""Verify WFH-ORG migration manifest invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FINAL_DISPOSITIONS = {"KEEP", "FIX_FIRST", "SUPERSEDED", "DROP", "QUARANTINE"}
ALLOWED_DISPOSITIONS = FINAL_DISPOSITIONS | {"UNREVIEWED"}
REQUIRED_FILE_FIELDS = {
    "source_repo",
    "source_sha",
    "source_path",
    "source_blob_sha",
    "mode",
    "disposition",
    "destination_path",
    "rationale",
    "verification",
}


def verify(data: dict, *, allow_unreviewed: bool) -> list[str]:
    errors: list[str] = []
    files = data.get("files", [])

    for item in files:
        for field in sorted(REQUIRED_FILE_FIELDS - item.keys()):
            errors.append(
                f"missing required field {field} for "
                f"{item.get('source_path', '<unknown>')}"
            )
        disposition = item.get("disposition")
        if disposition not in ALLOWED_DISPOSITIONS:
            errors.append(f"unknown disposition: {disposition}")

    if not allow_unreviewed:
        pending = [
            item.get("source_path", "<unknown>")
            for item in files
            if item.get("disposition") == "UNREVIEWED"
        ]
        if pending:
            errors.append(f"UNREVIEWED entries remain: {len(pending)}")

    declared_sources = {
        (str(item.get("repo")), str(item.get("sha"))): int(item.get("file_count", -1))
        for item in data.get("sources", [])
    }
    observed_counts: dict[tuple[str, str], int] = {}
    for item in files:
        key = (str(item.get("source_repo")), str(item.get("source_sha")))
        observed_counts[key] = observed_counts.get(key, 0) + 1
        if key not in declared_sources:
            errors.append(f"undeclared source: {key[0]}@{key[1]}")
    for key, expected_count in declared_sources.items():
        observed_count = observed_counts.get(key, 0)
        if observed_count != expected_count:
            errors.append(
                f"file count mismatch for {key[0]}@{key[1]}: "
                f"expected {expected_count}, observed {observed_count}"
            )

    sources: set[tuple[str, str, str]] = set()
    destinations: set[str] = set()
    for item in files:
        source_id = (
            str(item.get("source_repo")),
            str(item.get("source_sha")),
            str(item.get("source_path")),
        )
        if source_id in sources:
            errors.append("duplicate source: " + ":".join(source_id))
        sources.add(source_id)

        destination = item.get("destination_path")
        if not destination:
            continue
        if destination in destinations:
            errors.append(f"duplicate destination: {destination}")
        destinations.add(destination)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--allow-unreviewed", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = verify(data, allow_unreviewed=args.allow_unreviewed)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
