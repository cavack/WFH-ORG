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


def v2_target_file(**overrides: object) -> dict:
    item = {
        "path": "README.md",
        "blob_sha": "c" * 40,
        "mode": "100644",
        "disposition": "KEEP",
        "origin": "legacy_unchanged",
        "source_refs": ["cavack/wfh@" + "a" * 40 + ":README.md"],
        "rationale": "accepted canonical target",
        "verification": ["verified"],
    }
    item.update(overrides)
    return item


def manifest_v2(*entries: dict, target_files: list[dict]) -> dict:
    data = manifest_with(*entries)
    data["schema_version"] = 2
    data["target_files"] = target_files
    return data


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


    def test_strict_mode_requires_destination_and_verification_for_imported_file(self) -> None:
        entry = manifest_entry(
            disposition="KEEP",
            destination_path=None,
            rationale="accepted source file",
            verification=[],
        )
        result = self.run_verifier(manifest_with(entry))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("destination_path", result.stderr)
        self.assertIn("verification", result.stderr)

    def test_target_root_rejects_unmanifested_tracked_file(self) -> None:
        entry = manifest_entry(
            disposition="KEEP",
            destination_path="README.md",
            rationale="canonical readme",
            verification=["verified"],
        )
        manifest = manifest_with(entry)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            target = root / "target"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / "README.md").write_text("ok\n", encoding="utf-8")
            (target / "extra.txt").write_text("unmanifested\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(target), "add", "README.md", "extra.txt"], check=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    str(manifest_path),
                    "--target-root",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("unmanifested target path: extra.txt", result.stderr)


    def test_v2_target_root_rejects_blob_mismatch(self) -> None:
        entry = manifest_entry(
            disposition="KEEP",
            destination_path="README.md",
            rationale="canonical readme",
            verification=["verified"],
        )
        manifest = manifest_v2(entry, target_files=[v2_target_file(blob_sha="d" * 40)])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            target = root / "target"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / "README.md").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(target), "add", "README.md"], check=True)
            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(manifest_path), "--target-root", str(target)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("target blob mismatch: README.md", result.stderr)

    def test_v2_legacy_origin_requires_source_reference(self) -> None:
        entry = manifest_entry(
            disposition="KEEP",
            destination_path="README.md",
            rationale="canonical readme",
            verification=["verified"],
        )
        target = v2_target_file(source_refs=[])
        result = self.run_verifier(manifest_v2(entry, target_files=[target]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("source_refs required for legacy target", result.stderr)

    def test_v2_migration_generated_target_may_have_no_legacy_source(self) -> None:
        target = v2_target_file(
            path="migration/STATE.md",
            origin="migration_generated",
            disposition="KEEP",
            source_refs=[],
        )
        result = self.run_verifier(manifest_v2(target_files=[target]))
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_v2_non_manifest_target_requires_blob_sha(self) -> None:
        target = v2_target_file(
            blob_sha=None,
            origin="migration_generated",
            source_refs=[],
        )
        result = self.run_verifier(manifest_v2(target_files=[target]))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("blob_sha required for target file: README.md", result.stderr)

    def test_v2_manifest_may_omit_self_referential_blob_sha(self) -> None:
        target = v2_target_file(
            path="migration/source-manifest.json",
            blob_sha=None,
            origin="migration_control",
            source_refs=[],
        )
        result = self.run_verifier(manifest_v2(target_files=[target]))
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_v2_manifest_self_hash_exception_works_with_target_root(self) -> None:
        target_entry = v2_target_file(
            path="migration/source-manifest.json",
            blob_sha=None,
            origin="migration_control",
            source_refs=[],
        )
        manifest = manifest_v2(target_files=[target_entry])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            target = root / "target"
            (target / "migration").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / "migration/source-manifest.json").write_text("self\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(target), "add", "migration/source-manifest.json"], check=True)
            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(manifest_path), "--target-root", str(target)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
