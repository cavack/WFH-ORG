"""Tests for the fail-closed release certification gate.

The identities below are real pinned base-image digests from backend/Dockerfile
and frontend/Dockerfile in this repository; they are not placeholders.
"""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from waterfallhunter.core.release_certification_gate import CertificationStatus, ReleaseCertificationEvidence, evaluate_release_certification

BACKEND_PINNED_IMAGE = "python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a"
FRONTEND_PINNED_IMAGE = "node@sha256:aadf416b2cdce311a8811ba3f0608a61b77dbf997500e2eafe781b51f6a0b019"

def evidence(**overrides: object) -> ReleaseCertificationEvidence:
    values: dict[str, object] = {
        "git_sha": "8c2369f5da46eb50c70bb5a1010f24dae18142ed",
        "backend_image_digest": BACKEND_PINNED_IMAGE,
        "frontend_image_digest": FRONTEND_PINNED_IMAGE,
        "schema_version": 10,
        "schema_verified": True,
        "restore_drill_passed": True,
        "rollback_rehearsal_passed": True,
        "post_deploy_soak_passed": True,
        "oom_or_unexpected_restart_count": 0,
        "deterministic_security_gate_passed": True,
        "signal_only_verified": True,
        "live_trading_enabled": False,
    }
    values.update(overrides)
    return ReleaseCertificationEvidence.model_validate(values)

def test_complete_evidence_certifies_release() -> None:
    result = evaluate_release_certification(evidence())
    assert result.status is CertificationStatus.CERTIFIED
    assert result.reasons == ()

@pytest.mark.parametrize(("field", "reason"), [
    ("schema_verified", "SCHEMA_VERIFICATION_FAILED"),
    ("restore_drill_passed", "RESTORE_DRILL_NOT_PASSED"),
    ("rollback_rehearsal_passed", "ROLLBACK_REHEARSAL_NOT_PASSED"),
    ("post_deploy_soak_passed", "POST_DEPLOY_SOAK_NOT_PASSED"),
    ("deterministic_security_gate_passed", "DETERMINISTIC_SECURITY_GATE_NOT_PASSED"),
    ("signal_only_verified", "SIGNAL_ONLY_NOT_VERIFIED"),
])
def test_each_failed_gate_blocks_certification(field: str, reason: str) -> None:
    result = evaluate_release_certification(evidence(**{field: False}))
    assert result.status is CertificationStatus.NOT_CERTIFIED
    assert reason in result.reasons

def test_runtime_incident_and_live_trading_block_certification() -> None:
    result = evaluate_release_certification(evidence(oom_or_unexpected_restart_count=1, live_trading_enabled=True))
    assert result.status is CertificationStatus.NOT_CERTIFIED
    assert set(result.reasons) == {"RUNTIME_OOM_OR_UNEXPECTED_RESTART", "LIVE_TRADING_MUST_BE_DISABLED"}

def test_blank_identity_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        evidence(git_sha="   ")
