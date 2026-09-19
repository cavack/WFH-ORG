"""Fail-closed release, DR, and security certification gate.

This pure module certifies only supplied evidence. It does not deploy,
restore, access secrets, or execute orders. Missing evidence is failure.
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CertificationStatus(str, Enum):
    CERTIFIED = "CERTIFIED"
    NOT_CERTIFIED = "NOT_CERTIFIED"

class ReleaseCertificationEvidence(BaseModel):
    """Immutable evidence for one exact release artifact."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    git_sha: str
    backend_image_digest: str = Field(min_length=8)
    frontend_image_digest: str = Field(min_length=8)
    schema_version: int = Field(ge=1)
    schema_verified: bool
    restore_drill_passed: bool
    rollback_rehearsal_passed: bool
    post_deploy_soak_passed: bool
    oom_or_unexpected_restart_count: int = Field(ge=0)
    deterministic_security_gate_passed: bool
    signal_only_verified: bool
    live_trading_enabled: bool

    @field_validator("git_sha", "backend_image_digest", "frontend_image_digest")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("release identity evidence must not be blank")
        if value == value.strip() and value == "":
            raise ValueError("release identity evidence must not be blank")
        return value

    @field_validator("git_sha")
    @classmethod
    def git_sha_must_be_short_sha_or_longer(cls, value: str) -> str:
        if len(value) < 7:
            raise ValueError("git SHA must have at least 7 characters")
        return value

class ReleaseCertificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: CertificationStatus
    reasons: tuple[str, ...] = Field(default_factory=tuple)

def evaluate_release_certification(evidence: ReleaseCertificationEvidence) -> ReleaseCertificationResult:
    """Return CERTIFIED only if every real evidence fact passes."""
    checks = (
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
    return ReleaseCertificationResult(
        status=CertificationStatus.CERTIFIED if not reasons else CertificationStatus.NOT_CERTIFIED,
        reasons=reasons,
    )
