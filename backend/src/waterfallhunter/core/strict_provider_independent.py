"""Pure fail-closed alert-eligibility policy; no I/O or order execution.

This module answers two operator-facing questions from the same evidence set:

* May this candidate be surfaced as an alert at all? (``outcome``)
* If it is surfaced, is the evidence complete enough to be treated as a
  decision-grade statement, or must it be presented as research-only?

Neither answer may depend on one commercial provider being reachable.
CoinGlass-derived features are ``OPTIONAL``: their absence degrades the
evidence and is always reported, but it never blocks a candidate whose
mandatory evidence was fully observed.
"""
from __future__ import annotations
from enum import Enum
from typing import Mapping
from pydantic import BaseModel, ConfigDict, Field

# Machine-readable reason code for "the provider or feature is not available".
# Absence must always be explainable to the operator: this code states that the
# gap came from provider unavailability, not from a scoring or threshold choice.
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

# Reason recorded when a caller supplies no dependencies at all. With nothing
# evaluated, no correctness claim can be made, so the run fails closed.
NO_EVALUABLE_DEPENDENCIES = "no evaluable provider dependencies"


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

class DecisionGrade(str, Enum):
    """How a candidate's evidence may be presented to the human operator."""

    DECISION_GRADE = "DECISION_GRADE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    UNAVAILABLE = "UNAVAILABLE"

class FeatureDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    requirement: FeatureRequirement
    availability: FeatureAvailability
    reason: str | None = None
    reason_code: str | None = None

    def is_blocking(self) -> bool:
        return self.requirement is FeatureRequirement.MANDATORY and self.availability is FeatureAvailability.UNAVAILABLE

    def resolved_reason_code(self) -> str | None:
        """The machine-readable code to report, or ``None`` when available.

        A caller that forgets to set ``reason_code`` must not be able to hide the
        gap from the operator, so an unavailable feature always reports at least
        :data:`PROVIDER_UNAVAILABLE`.
        """
        if self.availability is not FeatureAvailability.UNAVAILABLE:
            return None
        code = (self.reason_code or "").strip()
        return code or PROVIDER_UNAVAILABLE

class ProviderIndependenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_version: str = "STRICT_PROVIDER_INDEPENDENT_V1"
    outcome: EligibilityOutcome
    decision_grade: DecisionGrade
    evaluated_features: tuple[str, ...] = Field(default_factory=tuple)
    blocking_features: tuple[str, ...] = Field(default_factory=tuple)
    degraded_optional_features: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)

def resolve_decision_grade(result: ProviderIndependenceResult) -> DecisionGrade:
    """Map an eligibility result onto an explicit, fail-closed decision grade.

    ``DECISION_GRADE`` requires that every evaluated dependency was observed.
    Any gap — mandatory or optional — downgrades the run to ``RESEARCH_ONLY``,
    and a result with nothing evaluated is ``UNAVAILABLE`` because no
    correctness claim can be made about it.
    """
    if not result.evaluated_features:
        return DecisionGrade.UNAVAILABLE
    if result.blocking_features or result.degraded_optional_features:
        return DecisionGrade.RESEARCH_ONLY
    return DecisionGrade.DECISION_GRADE

def evaluate_provider_independence(dependencies: Mapping[str, FeatureDependency]) -> ProviderIndependenceResult:
    """Classify evidence without silently accepting malformed or missing facts.

    An empty mapping is a contract failure, not a clean bill of health: with no
    dependencies evaluated there is no evidence to stand on, so the run is
    reported ``NOT_ALERT_GRADE`` / ``UNAVAILABLE`` rather than surfaced
    optimistically.
    """
    if not dependencies:
        return ProviderIndependenceResult(
            outcome=EligibilityOutcome.NOT_ALERT_GRADE,
            decision_grade=DecisionGrade.UNAVAILABLE,
            reasons=(NO_EVALUABLE_DEPENDENCIES,),
        )
    blocking: list[str] = []
    degraded: list[str] = []
    reasons: list[str] = []
    reason_codes: list[str] = []
    for name, dependency in dependencies.items():
        if name != dependency.name:
            raise ValueError(f"dependency mapping key '{name}' does not match dependency.name '{dependency.name}'")
        if dependency.availability is not FeatureAvailability.UNAVAILABLE:
            continue
        if not dependency.reason or not dependency.reason.strip():
            raise ValueError(f"feature '{name}' is UNAVAILABLE but has no reason; absence must always be explained, never assumed")
        reasons.append(f"{name}: {dependency.reason}")
        code = dependency.resolved_reason_code()
        if code:
            reason_codes.append(f"{name}: {code}")
        if dependency.is_blocking():
            blocking.append(name)
        else:
            degraded.append(name)
    result = ProviderIndependenceResult(
        outcome=EligibilityOutcome.NOT_ALERT_GRADE if blocking else EligibilityOutcome.ALERT_ELIGIBLE,
        decision_grade=DecisionGrade.UNAVAILABLE,
        evaluated_features=tuple(sorted(dependencies)),
        blocking_features=tuple(sorted(blocking)),
        degraded_optional_features=tuple(sorted(degraded)),
        reasons=tuple(sorted(reasons)),
        reason_codes=tuple(sorted(reason_codes)),
    )
    # Single source of truth: the grade is always derived by resolve_decision_grade.
    return result.model_copy(update={"decision_grade": resolve_decision_grade(result)})

def coinglass_dependency(*, available: bool, reason: str | None = None) -> FeatureDependency:
    """CoinGlass is OPTIONAL: absence degrades evidence but never silently disappears."""
    return FeatureDependency(
        name="coinglass_derivatives",
        requirement=FeatureRequirement.OPTIONAL,
        availability=FeatureAvailability.ACTIVE if available else FeatureAvailability.UNAVAILABLE,
        reason=None if available else reason or "CoinGlass provider unavailable",
        reason_code=None if available else PROVIDER_UNAVAILABLE,
    )
