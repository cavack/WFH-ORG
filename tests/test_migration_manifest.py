import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_migration_manifest.py"


def manifest_entry(**overrides: object) -> dict:
    entry = {
        "source_repo": "cavack/wfh",
        "source_sha": "a" * 40,
        "source_path": "README.md",
        "source_blob_sha": "b" * 40,
        "mode": "100644",
        "disposition": "UNREVIEWED",
        "destination_path": None,
        "rationale": "pending review",
        "verification": [],
    }
    entry.update(overrides)
    return entry


def manifest_with(*entries: dict) -> dict:
    counts: dict[tuple[str, str], int] = {}
    for entry in entries:
        key = (str(entry["source_repo"]), str(entry["source_sha"]))
        counts[key] = counts.get(key, 0) + 1
    sources = [
        {"repo": repo, "sha": sha, "file_count": count, "role": "test"}
        for (repo, sha), count in counts.items()
    ]
    return {"schema_version": 1, "sources": sources, "files": list(entries)}


class MigrationManifestVerifierTests(unittest.TestCase):
    def run_verifier(self, manifest: dict, *extra: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(VERIFIER), str(path), *extra],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_strict_mode_rejects_unreviewed_entry(self) -> None:
        result = self.run_verifier(manifest_with(manifest_entry()))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("UNREVIEWED", result.stderr)

    def test_inventory_mode_allows_unreviewed_entry(self) -> None:
        result = self.run_verifier(
            manifest_with(manifest_entry()),
            "--allow-unreviewed",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_destination_is_rejected(self) -> None:
        first = manifest_entry(
            disposition="KEEP",
            destination_path="README.md",
            rationale="canonical readme",
        )
        second = manifest_entry(
            source_path="docs/README.md",
            source_blob_sha="c" * 40,
            disposition="KEEP",
            destination_path="README.md",
            rationale="conflicting destination",
        )
        result = self.run_verifier(manifest_with(first, second))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("duplicate destination", result.stderr.lower())

    def test_unknown_disposition_is_rejected(self) -> None:
        entry = manifest_entry(
            disposition="COPY_IT",
            destination_path="README.md",
        )
        result = self.run_verifier(manifest_with(entry), "--allow-unreviewed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("unknown disposition", result.stderr.lower())

    def test_duplicate_source_identity_is_rejected(self) -> None:
        first = manifest_entry()
        second = copy.deepcopy(first)
        result = self.run_verifier(
            manifest_with(first, second),
            "--allow-unreviewed",
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("duplicate source", result.stderr.lower())

    def test_declared_source_file_count_must_match_entries(self) -> None:
        manifest = manifest_with(manifest_entry())
        manifest["sources"] = [
            {
                "repo": "cavack/wfh",
                "sha": "a" * 40,
                "file_count": 2,
                "role": "primary",
            }
        ]
        result = self.run_verifier(manifest, "--allow-unreviewed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("file count mismatch", result.stderr.lower())

    def test_file_from_undeclared_source_is_rejected(self) -> None:
        manifest = manifest_with(manifest_entry())
        manifest["sources"] = []
        result = self.run_verifier(manifest, "--allow-unreviewed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("undeclared source", result.stderr.lower())

    def test_missing_required_file_field_is_rejected(self) -> None:
        entry = manifest_entry()
        del entry["source_blob_sha"]
        result = self.run_verifier(manifest_with(entry), "--allow-unreviewed")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("missing required field", result.stderr.lower())
        self.assertIn("source_blob_sha", result.stderr)


if __name__ == "__main__":
    unittest.main()
