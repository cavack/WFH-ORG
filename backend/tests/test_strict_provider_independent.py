"""Fail-closed tests for STRICT_PROVIDER_INDEPENDENT_V1."""
from __future__ import annotations
import pytest
from waterfallhunter.core.strict_provider_independent import (
    EligibilityOutcome, FeatureAvailability, FeatureDependency,
    FeatureRequirement, coinglass_dependency, evaluate_provider_independence,
)

def dependency(name: str, requirement: FeatureRequirement, availability: FeatureAvailability, reason: str | None = None) -> FeatureDependency:
    return FeatureDependency(name=name, requirement=requirement, availability=availability, reason=reason)

def test_optional_unavailable_is_alert_eligible_and_preserves_reason() -> None:
    result = evaluate_provider_independence({
        "coinglass_derivatives": coinglass_dependency(available=False, reason="CoinGlass API key unavailable"),
        "structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.ACTIVE),
    })
    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert result.blocking_features == ()
    assert result.degraded_optional_features == ("coinglass_derivatives",)
    assert result.reasons == ("coinglass_derivatives: CoinGlass API key unavailable",)

def test_mandatory_unavailable_forces_not_alert_grade() -> None:
    result = evaluate_provider_independence({
        "structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.UNAVAILABLE, "structure evidence unavailable"),
        "coinglass_derivatives": coinglass_dependency(available=True),
    })
    assert result.outcome is EligibilityOutcome.NOT_ALERT_GRADE
    assert result.blocking_features == ("structure",)
    assert result.reasons == ("structure: structure evidence unavailable",)

@pytest.mark.parametrize("reason", [None, "", "   \t  "])
def test_unavailable_without_nonblank_reason_is_rejected(reason: str | None) -> None:
    with pytest.raises(ValueError, match="no reason"):
        evaluate_provider_independence({"structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.UNAVAILABLE, reason)})

def test_mapping_key_must_match_dependency_name() -> None:
    with pytest.raises(ValueError, match="does not match"):
        evaluate_provider_independence({"structure": dependency("timing", FeatureRequirement.MANDATORY, FeatureAvailability.UNAVAILABLE, "stale")})

def test_excluded_unavailable_is_degraded_and_preserves_reason() -> None:
    result = evaluate_provider_independence({
        "legacy": dependency("legacy", FeatureRequirement.EXCLUDED_FROM_STRICT, FeatureAvailability.UNAVAILABLE, "provider retired"),
        "structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.ACTIVE),
    })
    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert result.degraded_optional_features == ("legacy",)
    assert result.reasons == ("legacy: provider retired",)

def test_all_active_dependencies_are_clean() -> None:
    result = evaluate_provider_independence({
        "structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.ACTIVE),
        "coinglass_derivatives": coinglass_dependency(available=True),
    })
    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert result.degraded_optional_features == ()
    assert result.reasons == ()

def test_multiple_blockers_are_sorted() -> None:
    result = evaluate_provider_independence({
        "timing": dependency("timing", FeatureRequirement.MANDATORY, FeatureAvailability.UNAVAILABLE, "timing unavailable"),
        "structure": dependency("structure", FeatureRequirement.MANDATORY, FeatureAvailability.UNAVAILABLE, "structure unavailable"),
    })
    assert result.blocking_features == ("structure", "timing")
    assert result.reasons == ("structure: structure unavailable", "timing: timing unavailable")

def test_coinglass_dependency_contract() -> None:
    assert coinglass_dependency(available=True).reason is None
    unavailable = coinglass_dependency(available=False)
    assert unavailable.requirement is FeatureRequirement.OPTIONAL
    assert unavailable.reason == "CoinGlass provider unavailable"
