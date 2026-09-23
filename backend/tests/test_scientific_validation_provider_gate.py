"""STRICT_PROVIDER_INDEPENDENT_V1 wired into scientific validation review.

The follow-up contract from docs/STRICT_PROVIDER_INDEPENDENT_V1.md: a cohort
whose CoinGlass dependency is UNAVAILABLE (OPTIONAL gap) stays eligible for
validated review — the gap is recorded in the report, not hidden — while a
cohort with a MANDATORY dependency gap is not eligible at all.

RED/GREEN: written first; fails with ``TypeError`` (unexpected keyword
``provider_dependencies``) until the wiring exists. Callers that declare no
provider context keep byte-identical reports (back-compat contract).
"""

from __future__ import annotations

from test_scientific_validation import _request

from waterfallhunter.core.scientific_validation import (
    validate_strict_scientific_evidence,
)
from waterfallhunter.core.strict_provider_independent import (
    FeatureAvailability,
    FeatureDependency,
    FeatureRequirement,
    coinglass_dependency,
)


def test_coinglass_unavailable_cohort_stays_eligible_for_owner_review() -> None:
    report = validate_strict_scientific_evidence(
        _request(),
        provider_dependencies={
            "coinglass_derivatives": coinglass_dependency(available=False),
        },
    )

    # OPTIONAL gap must never block validated review (Issue #20 reality).
    assert report["evidence_gate_status"] == "COMPLETE_FOR_OWNER_REVIEW"
    assert report["promotion_decision"] == "OWNER_REVIEW_REQUIRED"
    independence = report["provider_independence"]
    assert independence["policy_version"] == "STRICT_PROVIDER_INDEPENDENT_V1"
    assert independence["outcome"] == "ALERT_ELIGIBLE"
    assert independence["decision_grade"] == "RESEARCH_ONLY"
    assert independence["blocking_features"] == []
    assert independence["degraded_optional_features"] == ["coinglass_derivatives"]
    assert (
        "coinglass_derivatives: PROVIDER_UNAVAILABLE" in independence["reason_codes"]
    )


def test_mandatory_dependency_gap_blocks_validated_review() -> None:
    report = validate_strict_scientific_evidence(
        _request(),
        provider_dependencies={
            "coinglass_derivatives": coinglass_dependency(available=True),
            "structure": FeatureDependency(
                name="structure",
                requirement=FeatureRequirement.MANDATORY,
                availability=FeatureAvailability.UNAVAILABLE,
                reason="structure evidence unavailable for the cohort window",
                reason_code="STRUCTURE_UNAVAILABLE",
            ),
        },
    )

    assert report["evidence_gate_status"] == "INSUFFICIENT"
    assert report["promotion_decision"] == "DO_NOT_PROMOTE"
    assert (
        "PROVIDER_EVIDENCE_MANDATORY_FEATURE_UNAVAILABLE"
        in report["blocking_reasons"]
    )
    assert report["provider_independence"]["blocking_features"] == ["structure"]
    assert report["provider_independence"]["outcome"] == "NOT_ALERT_GRADE"


def test_empty_declared_dependency_map_fails_closed() -> None:
    report = validate_strict_scientific_evidence(
        _request(),
        provider_dependencies={},
    )

    # Nothing evaluated means nothing to claim: review is not granted.
    assert report["evidence_gate_status"] == "INSUFFICIENT"
    assert report["promotion_decision"] == "DO_NOT_PROMOTE"
    assert report["provider_independence"]["decision_grade"] == "UNAVAILABLE"


def test_undeclared_provider_dependencies_keep_report_byte_identical() -> None:
    report = validate_strict_scientific_evidence(_request())

    # Back-compat: callers with no provider context get the pre-existing
    # report shape unchanged — no half-populated evaluation is invented.
    assert "provider_independence" not in report
    assert report["evidence_gate_status"] == "COMPLETE_FOR_OWNER_REVIEW"
