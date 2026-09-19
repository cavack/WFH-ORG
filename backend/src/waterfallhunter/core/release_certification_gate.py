"""Pure fail-closed release certification policy; it performs no deployment."""
from __future__ import annotations
import re
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from waterfallhunter.core.schema_contract import CURRENT_RUNTIME_SCHEMA_VERSION

_SHA = re.compile(r"^[0-9a-f]{7,64}$")
_IMAGE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")

class CertificationStatus(str, Enum):
    CERTIFIED = "CERTIFIED"
    NOT_CERTIFIED = "NOT_CERTIFIED"

class ReleaseCertificationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    git_sha: str
    backend_image_digest: str
    frontend_image_digest: str
    artifact_identity_verified: StrictBool
    schema_version: int = Field(ge=1)
    schema_verified: StrictBool
    restore_drill_passed: StrictBool
    rollback_rehearsal_passed: StrictBool
    post_deploy_soak_passed: StrictBool
    oom_or_unexpected_restart_count: int = Field(ge=0)
    deterministic_security_gate_passed: StrictBool
    signal_only_verified: StrictBool
    live_trading_enabled: StrictBool

    @field_validator("git_sha")
    @classmethod
    def git_sha_must_be_verifiable(cls, value: str) -> str:
        if not _SHA.fullmatch(value):
            raise ValueError("git_sha must be a 7-64 character lowercase hexadecimal SHA")
        return value

    @field_validator("backend_image_digest", "frontend_image_digest")
    @classmethod
    def image_must_be_immutable_digest(cls, value: str) -> str:
        if not _IMAGE.fullmatch(value):
            raise ValueError("image identity must contain an immutable @sha256: 64-hex digest")
        return value

class ReleaseCertificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: CertificationStatus
    reasons: tuple[str, ...] = Field(default_factory=tuple)

def evaluate_release_certification(evidence: ReleaseCertificationEvidence) -> ReleaseCertificationResult:
    checks = (
        (evidence.artifact_identity_verified, "ARTIFACT_IDENTITY_NOT_VERIFIED"),
        (evidence.schema_version == CURRENT_RUNTIME_SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH"),
        (evidence.schema_verified, "SCHEMA_VERIFICATION_FAILED"),
        (evidence.restore_drill_passed, "RESTORE_DRILL_NOT_PASSED"),
        (evidence.rollback_rehearsal_passed, "ROLLBACK_REHEARSAL_NOT_PASSED"),
        (evidence.post_deploy_soak_passed, "POST_DEPLOY_SOAK_NOT_PASSED"),
        (evidence.oom_or_unexpected_restart_count == 0, "RUNTIME_OOM_OR_UNEXPECTED_RESTART"),
        (evidence.deterministic_security_gate_passed, "DETERMINISTIC_SECURITY_GATE_NOT_PASSED"),
        (evidence.signal_only_verified, "SIGNAL_ONLY_NOT_VERIFIED"),
        (not evidence.live_trading_enabled, "LIVE_TRADING_MUST_BE_DISABLED"),
    )
    reasons = tuple(reason for passed, reason in checks if not passed)
    return ReleaseCertificationResult(CertificationStatus.CERTIFIED if not reasons else CertificationStatus.NOT_CERTIFIED, reasons)
