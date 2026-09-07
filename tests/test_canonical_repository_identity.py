import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPOSITORY = "cavack/WFH-ORG"
CANONICAL_URL = "https://github.com/cavack/WFH-ORG"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class CanonicalRepositoryIdentityTests(unittest.TestCase):
    def test_runtime_and_artifact_identity_points_to_wfh_org(self) -> None:
        self.assertIn(f'CANONICAL_REPOSITORY = "{CANONICAL_REPOSITORY}"', _read("scripts/wfh_mission.py"))
        self.assertIn(f'WFH_OCI_SOURCE = "{CANONICAL_URL}"', _read("scripts/audit_host_inventory.py"))
        self.assertIn(f'"canonical_repository": "{CANONICAL_REPOSITORY}"', _read("scripts/export_chatgpt_project_sources.py"))
        for path in ("backend/Dockerfile", "frontend/Dockerfile", "watchdog/Dockerfile"):
            self.assertIn(f'org.opencontainers.image.source="{CANONICAL_URL}"', _read(path), path)

    def test_canonical_user_surfaces_point_to_wfh_org(self) -> None:
        expected = f"phrase=ادامه کار گروهی | project=TWFH | repository={CANONICAL_REPOSITORY} |"
        for path in (
            "AGENTS.md",
            "docs/chatgpt-project/PROJECT-INSTRUCTIONS-v2.txt",
            "docs/chatgpt-project/00-WFH-CHATGPT-ROUTER-v2.md",
            "docs/chatgpt-project/TWFH-RESUME.md",
        ):
            self.assertIn(expected, _read(path), path)
        self.assertIn(f"{CANONICAL_URL}/security/advisories/new", _read(".github/ISSUE_TEMPLATE/config.yml"))


if __name__ == "__main__":
    unittest.main()
