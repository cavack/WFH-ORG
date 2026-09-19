"""STRICT_PROVIDER_INDEPENDENT_V1 policy.

WaterfallHunter / WFH-ORG is a manual-action signal-alert system: it
continuously evaluates candidates and surfaces alerts for a human operator
to act on. The operator decides and executes manually; the system itself
never places or automates order execution (LIVE_TRADING_ENABLED=false).

This module defines the evidence-completeness contract that determines
whether a STRICT candidate is reliable enough to be surfaced to the
operator as an actionable alert (ALERT_ELIGIBLE), even when an optional
derivatives provider (for example CoinGlass) is UNAVAILABLE.

Core rules (see docs/STRICT_PROVIDER_INDEPENDENT_V1.md for rationale):

1. A feature or provider being UNAVAILABLE is never silently treated as
   zero, neutral, or forward-filled. Absence must remain explicit.
2. A candidate that depends on a MANDATORY feature which is UNAVAILABLE
   cannot be certified ALERT_ELIGIBLE. It is downgraded to
   NOT_ALERT_GRADE with an explicit reason. NOT_ALERT_GRADE means the
   evidence is currently too incomplete or unreliable to alert the
   operator — it is a data-quality gate, not a statement that the
   candidate is only fit for academic study.
3. A candidate that depends only on OPTIONAL or EXCLUDED_FROM_STRICT
   features may remain ALERT_ELIGIBLE even when those features are
   UNAVAILABLE, as long as the dependency gap is recorded.
4. Replay must reproduce the same availability/eligibility outcome as
   the original decision for the same inputs (determinism), not merely
   the same idempotent row.

This module does not fetch data, call providers, or place orders. It is
a pure policy/classification layer consumed by scoring, validation, and
replay code. It has no dependency on network I/O, the database, or the
notification/alerting transport.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field


class FeatureRequirement(str, Enum):
    """How a named feature participates in the STRICT alert-eligibility contract."""

    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    EXCLUDED_FROM_STRICT = "EXCLUDED_FROM_STRICT"


class FeatureAvailability(str, Enum):
    """Observed availability of one feature/provider for one evaluation."""

    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


class EligibilityOutcome(str, Enum):
    """Result of applying the provider-independence alert-eligibility policy."""

    ALERT_ELIGIBLE = "ALERT_ELIGIBLE"
    NOT_ALERT_GRADE = "NOT_ALERT_GRADE"


class FeatureDependency(BaseModel):
    """One feature's requirement level and observed availability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    requirement: FeatureRequirement
    availability: FeatureAvailability
    reason: str | None = Field(
        default=None,
        description=(
            "Required when availability is UNAVAILABLE; must be a stable, "
            "non-empty machine-readable reason code (e.g. "
            "'CoinGlass API key unavailable')."
        ),
    )

    def is_blocking(self) -> bool:
        """A MANDATORY feature that is UNAVAILABLE always blocks alert eligibility."""
        return (
            self.requirement is FeatureRequirement.MANDATORY
            and self.availability is FeatureAvailability.UNAVAILABLE
        )


class ProviderIndependenceResult(BaseModel):
    """Outcome of evaluating one candidate against STRICT_PROVIDER_INDEPENDENT_V1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str = Field(default="STRICT_PROVIDER_INDEPENDENT_V1")
    outcome: EligibilityOutcome
    blocking_features: tuple[str, ...] = Field(default_factory=tuple)
    degraded_optional_features: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)


def evaluate_provider_independence(
    dependencies: Mapping[str, FeatureDependency],
) -> ProviderIndependenceResult:
    """Apply STRICT_PROVIDER_INDEPENDENT_V1 to one candidate's dependencies.

    Parameters
    ----------
    dependencies:
        Mapping of feature name to its :class:`FeatureDependency`. Keys must
        match ``dependency.name`` for each value (enforced by callers via
        tests, not by this function, to keep this layer stateless).

    Returns
    -------
    ProviderIndependenceResult
        ``ALERT_ELIGIBLE`` only if no MANDATORY feature is UNAVAILABLE.
        Any UNAVAILABLE MANDATORY feature forces ``NOT_ALERT_GRADE`` and is
        listed in ``blocking_features``. UNAVAILABLE OPTIONAL or
        EXCLUDED_FROM_STRICT features never block alert eligibility but are
        listed in ``degraded_optional_features`` so completeness stays
        observable to the operator.

    Raises
    ------
    ValueError
        If any dependency is UNAVAILABLE without a non-empty ``reason``.
        Absence must always be explained, never assumed.
    """

    blocking: list[str] = []
    degraded: list[str] = []
    reasons: list[str] = []

    for name, dependency in dependencies.items():
        if dependency.availability is FeatureAvailability.UNAVAILABLE:
            if not dependency.reason:
                raise ValueError(
                    f"feature '{name}' is UNAVAILABLE but has no reason; "
                    "absence must always be explained, never assumed"
                )
            if dependency.is_blocking():
                blocking.append(name)
                reasons.append(f"{name}: {dependency.reason}")
            elif dependency.requirement in (
                FeatureRequirement.OPTIONAL,
                FeatureRequirement.EXCLUDED_FROM_STRICT,
            ):
                degraded.append(name)

    if blocking:
        return ProviderIndependenceResult(
            outcome=EligibilityOutcome.NOT_ALERT_GRADE,
            blocking_features=tuple(sorted(blocking)),
            degraded_optional_features=tuple(sorted(degraded)),
            reasons=tuple(reasons),
        )

    return ProviderIndependenceResult(
        outcome=EligibilityOutcome.ALERT_ELIGIBLE,
        blocking_features=(),
        degraded_optional_features=tuple(sorted(degraded)),
        reasons=(),
    )


def coinglass_dependency(*, available: bool, reason: str | None = None) -> FeatureDependency:
    """Build the CoinGlass dependency as OPTIONAL under this policy.

    CoinGlass-derived features (funding, open interest, crowding) are
    classified OPTIONAL for STRICT_PROVIDER_INDEPENDENT_V1: their absence
    must never silently zero-fill a score component, but it also must not
    block an otherwise complete candidate from being surfaced as an alert.
    Any consumer that treats a CoinGlass-derived component as MANDATORY
    must construct its own FeatureDependency with
    FeatureRequirement.MANDATORY and accept that alert eligibility will
    degrade to NOT_ALERT_GRADE while the provider is UNAVAILABLE.
    """

    if available:
        return FeatureDependency(
            name="coinglass_derivatives",
            requirement=FeatureRequirement.OPTIONAL,
            availability=FeatureAvailability.ACTIVE,
            reason=None,
        )
    return FeatureDependency(
        name="coinglass_derivatives",
        requirement=FeatureRequirement.OPTIONAL,
        availability=FeatureAvailability.UNAVAILABLE,
        reason=reason or "CoinGlass provider unavailable",
    )
