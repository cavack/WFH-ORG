"""Fail-closed tests for STRICT_PROVIDER_INDEPENDENT_V1.

These tests assert the alert-eligibility policy contract in
backend/src/waterfallhunter/core/strict_provider_independent.py:

- CoinGlass UNAVAILABLE never blocks alert eligibility (it is OPTIONAL).
- Any MANDATORY feature UNAVAILABLE forces NOT_ALERT_GRADE.
- UNAVAILABLE without a reason is rejected (no silent absence).
- Availability is never coerced into a zero/neutral value by this layer.
- Outcomes use ALERT_ELIGIBLE / NOT_ALERT_GRADE, matching the manual-action
  signal-alert framing of the product (not a passive research label).
"""

from __future__ import annotations

import pytest

from waterfallhunter.core.strict_provider_independent import (
    EligibilityOutcome,
    FeatureAvailability,
    FeatureDependency,
    FeatureRequirement,
    coinglass_dependency,
    evaluate_provider_independence,
)


def test_coinglass_unavailable_does_not_block_alert_eligibility() -> None:
    dependencies = {
        "coinglass_derivatives": coinglass_dependency(
            available=False, reason="CoinGlass API key unavailable"
        ),
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.ACTIVE,
        ),
    }

    result = evaluate_provider_independence(dependencies)

    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert result.blocking_features == ()
    assert "coinglass_derivatives" in result.degraded_optional_features


def test_mandatory_feature_unavailable_forces_not_alert_grade() -> None:
    dependencies = {
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.UNAVAILABLE,
            reason="structure evidence unavailable",
        ),
        "coinglass_derivatives": coinglass_dependency(available=True),
    }

    result = evaluate_provider_independence(dependencies)

    assert result.outcome is EligibilityOutcome.NOT_ALERT_GRADE
    assert result.blocking_features == ("structure",)
    assert any("structure evidence unavailable" in reason for reason in result.reasons)


def test_unavailable_without_reason_is_rejected() -> None:
    dependencies = {
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.UNAVAILABLE,
            reason=None,
        ),
    }

    with pytest.raises(ValueError, match="no reason"):
        evaluate_provider_independence(dependencies)


def test_excluded_from_strict_feature_unavailable_is_degraded_not_blocking() -> None:
    dependencies = {
        "legacy_experimental_signal": FeatureDependency(
            name="legacy_experimental_signal",
            requirement=FeatureRequirement.EXCLUDED_FROM_STRICT,
            availability=FeatureAvailability.UNAVAILABLE,
            reason="legacy provider retired",
        ),
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.ACTIVE,
        ),
    }

    result = evaluate_provider_independence(dependencies)

    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert "legacy_experimental_signal" in result.degraded_optional_features


def test_all_active_dependencies_have_no_degraded_features() -> None:
    dependencies = {
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.ACTIVE,
        ),
        "coinglass_derivatives": coinglass_dependency(available=True),
    }

    result = evaluate_provider_independence(dependencies)

    assert result.outcome is EligibilityOutcome.ALERT_ELIGIBLE
    assert result.degraded_optional_features == ()
    assert result.reasons == ()


def test_multiple_mandatory_features_unavailable_are_all_listed() -> None:
    dependencies = {
        "structure": FeatureDependency(
            name="structure",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.UNAVAILABLE,
            reason="structure evidence unavailable",
        ),
        "timing": FeatureDependency(
            name="timing",
            requirement=FeatureRequirement.MANDATORY,
            availability=FeatureAvailability.UNAVAILABLE,
            reason="timing evidence unavailable",
        ),
    }

    result = evaluate_provider_independence(dependencies)

    assert result.outcome is EligibilityOutcome.NOT_ALERT_GRADE
    assert set(result.blocking_features) == {"structure", "timing"}


def test_coinglass_dependency_active_has_no_reason() -> None:
    dependency = coinglass_dependency(available=True)

    assert dependency.availability is FeatureAvailability.ACTIVE
    assert dependency.requirement is FeatureRequirement.OPTIONAL
    assert dependency.reason is None


def test_coinglass_dependency_unavailable_defaults_to_stable_reason() -> None:
    dependency = coinglass_dependency(available=False)

    assert dependency.availability is FeatureAvailability.UNAVAILABLE
    assert dependency.reason == "CoinGlass provider unavailable"
