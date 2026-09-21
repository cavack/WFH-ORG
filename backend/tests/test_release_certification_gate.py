"""Fail-closed tests for release certification evidence."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from waterfallhunter.core.release_certification_gate import CertificationStatus, ReleaseCertificationEvidence, evaluate_release_certification
from waterfallhunter.core.schema_contract import CURRENT_RUNTIME_SCHEMA_VERSION

BACKEND = "python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a"
FRONTEND = "node@sha256:aadf416b2cdce311a8811ba3f0608a61b77dbf997500e2eafe781b51f6a0b019"

def evidence(**overrides: object) -> ReleaseCertificationEvidence:
    values: dict[str, object] = {
        "git_sha": "8c2369f5da46eb50c70bb5a1010f24dae18142ed",
        "backend_image_digest": BACKEND, "frontend_image_digest": FRONTEND,
        "artifact_identity_verified": True, "schema_version": CURRENT_RUNTIME_SCHEMA_VERSION,
        "schema_verified": True, "restore_drill_passed": True,
        "rollback_rehearsal_passed": True, "post_deploy_soak_passed": True,
        "oom_or_unexpected_restart_count": 0, "deterministic_security_gate_passed": True,
        "signal_only_verified": True, "live_trading_enabled": False,
    }
    values.update(overrides)
    return ReleaseCertificationEvidence.model_validate(values)

def test_complete_real_evidence_certifies() -> None:
    assert evaluate_release_certification(evidence()).status is CertificationStatus.CERTIFIED

@pytest.mark.parametrize(("schema_version"), [CURRENT_RUNTIME_SCHEMA_VERSION - 1, CURRENT_RUNTIME_SCHEMA_VERSION + 1])
def test_stale_or_future_schema_cannot_certify(schema_version: int) -> None:
    result = evaluate_release_certification(evidence(schema_version=schema_version))
    assert result.status is CertificationStatus.NOT_CERTIFIED
    assert "SCHEMA_VERSION_MISMATCH" in result.reasons

@pytest.mark.parametrize(("field", "value"), [("git_sha", "not-a-sha"), ("backend_image_digest", "python:3.13"), ("frontend_image_digest", "node@sha256:abc")])
def test_unverifiable_artifact_identity_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        evidence(**{field: value})

@pytest.mark.parametrize("field", ["artifact_identity_verified", "schema_verified", "restore_drill_passed", "rollback_rehearsal_passed", "post_deploy_soak_passed", "deterministic_security_gate_passed", "signal_only_verified", "live_trading_enabled"])
@pytest.mark.parametrize("value", ["yes", 1])
def test_boolean_evidence_is_strict(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        evidence(**{field: value})

def test_unverified_identity_blocks_certification() -> None:
    result = evaluate_release_certification(evidence(artifact_identity_verified=False))
    assert result.status is CertificationStatus.NOT_CERTIFIED
    assert "ARTIFACT_IDENTITY_NOT_VERIFIED" in result.reasons

def test_runtime_and_signal_safety_fail_closed() -> None:
    result = evaluate_release_certification(evidence(oom_or_unexpected_restart_count=1, live_trading_enabled=True))
    assert set(result.reasons) == {"RUNTIME_OOM_OR_UNEXPECTED_RESTART", "LIVE_TRADING_MUST_BE_DISABLED"}
