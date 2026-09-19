"""Pure fail-closed alert-eligibility policy; no I/O or order execution."""
from __future__ import annotations
from enum import Enum
from typing import Mapping
from pydantic import BaseModel, ConfigDict, Field

class FeatureRequirement(str, Enum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    EXCLUDED_FROM_STRICT = "EXCLUDED_FROM_STRICT"

class FeatureAvailability(str, Enum):
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"

class EligibilityOutcome(str, Enum):
    ALERT_ELIGIBLE = "ALERT_ELIGIBLE"
    NOT_ALERT_GRADE = "NOT_ALERT_GRADE"

class FeatureDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    requirement: FeatureRequirement
    availability: FeatureAvailability
    reason: str | None = None

    def is_blocking(self) -> bool:
        return self.requirement is FeatureRequirement.MANDATORY and self.availability is FeatureAvailability.UNAVAILABLE

class ProviderIndependenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_version: str = "STRICT_PROVIDER_INDEPENDENT_V1"
    outcome: EligibilityOutcome
    blocking_features: tuple[str, ...] = Field(default_factory=tuple)
    degraded_optional_features: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)

def evaluate_provider_independence(dependencies: Mapping[str, FeatureDependency]) -> ProviderIndependenceResult:
    """Classify evidence without silently accepting malformed or missing facts."""
    blocking: list[str] = []
    degraded: list[str] = []
    reasons: list[str] = []
    for name, dependency in dependencies.items():
        if name != dependency.name:
            raise ValueError(f"dependency mapping key '{name}' does not match dependency.name '{dependency.name}'")
        if dependency.availability is not FeatureAvailability.UNAVAILABLE:
            continue
        if not dependency.reason or not dependency.reason.strip():
            raise ValueError(f"feature '{name}' is UNAVAILABLE but has no reason; absence must always be explained, never assumed")
        reasons.append(f"{name}: {dependency.reason}")
        if dependency.is_blocking():
            blocking.append(name)
        else:
            degraded.append(name)
    return ProviderIndependenceResult(
        outcome=EligibilityOutcome.NOT_ALERT_GRADE if blocking else EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=tuple(sorted(blocking)),
        degraded_optional_features=tuple(sorted(degraded)),
        reasons=tuple(sorted(reasons)),
    )

def coinglass_dependency(*, available: bool, reason: str | None = None) -> FeatureDependency:
    """CoinGlass is OPTIONAL: absence degrades evidence but never silently disappears."""
    return FeatureDependency(
        name="coinglass_derivatives",
        requirement=FeatureRequirement.OPTIONAL,
        availability=FeatureAvailability.ACTIVE if available else FeatureAvailability.UNAVAILABLE,
        reason=None if available else reason or "CoinGlass provider unavailable",
    )
