"""Tests for provenance."""

from datetime import UTC
from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.provenance import Confidence
from app.domain.provenance import Provenance
from app.domain.provenance import ReferenceSource
from app.domain.provenance import SourceType


def test_all_source_types_present() -> None:
    assert {s.value for s in SourceType} == {
        "OREDA",
        "ISO_14224",
        "USER_DEFINED",
        "AI_ESTIMATE",
        "ENGINEERING_ASSUMPTION",
        "HISTORICAL_DATA",
        "MANUFACTURER_DATA",
    }


@pytest.mark.parametrize(
    "source",
    [
        SourceType.OREDA,
        SourceType.ISO_14224,
        SourceType.HISTORICAL_DATA,
        SourceType.MANUFACTURER_DATA,
    ],
)
def test_reference_is_required_for_documented_sources(
    source: SourceType,
) -> None:
    with pytest.raises(PydanticValidationError):
        Provenance(source_type=source)
    with pytest.raises(PydanticValidationError):
        Provenance(source_type=source, source_reference="  ")
    ok = Provenance(source_type=source, source_reference="OREDA 2015 p.12")
    assert ok.source_reference == "OREDA 2015 p.12"


def test_ai_estimate_cannot_be_high_confidence() -> None:
    with pytest.raises(PydanticValidationError):
        Provenance(
            source_type=SourceType.AI_ESTIMATE, confidence=Confidence.HIGH
        )


def test_generated_at_must_be_timezone_aware() -> None:
    with pytest.raises(PydanticValidationError):
        Provenance(
            source_type=SourceType.USER_DEFINED,
            generated_at=datetime(2026, 1, 1),
        )
    ok = Provenance(
        source_type=SourceType.USER_DEFINED,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert ok.generated_at is not None


def test_fabricate_estimate_is_low_confidence_synthetic() -> None:
    prov = Provenance.fabricate_estimate("conv-123")
    assert prov.source_type is SourceType.AI_ESTIMATE
    assert prov.generated_by == "fabricate"
    assert prov.confidence is Confidence.LOW
    assert prov.source_reference == "conv-123"
    assert prov.is_synthetic
    assert prov.is_estimate
    assert prov.generated_at is not None


def test_user_defined_is_not_an_estimate() -> None:
    prov = Provenance.user_defined("alice")
    assert prov.source_type is SourceType.USER_DEFINED
    assert prov.generated_by == "alice"
    assert not prov.is_estimate
    assert not prov.is_synthetic


def test_engineering_assumption_is_estimate_but_not_synthetic() -> None:
    prov = Provenance(source_type=SourceType.ENGINEERING_ASSUMPTION)
    assert prov.is_estimate
    assert not prov.is_synthetic


def test_provenance_is_frozen() -> None:
    prov = Provenance.user_defined()
    with pytest.raises(PydanticValidationError):
        prov.confidence = Confidence.HIGH  # type: ignore[misc]


def test_reference_source() -> None:
    src = ReferenceSource(source_type=SourceType.OREDA, title="OREDA Handbook")
    assert src.id is not None
    with pytest.raises(PydanticValidationError):
        ReferenceSource(source_type=SourceType.OREDA, title="")


def test_oreda_and_iso_factories() -> None:
    oreda = Provenance.oreda("table 4.1 p.12")
    assert oreda.source_type is SourceType.OREDA
    assert oreda.confidence is Confidence.HIGH
    iso = Provenance.iso14224("code PUMP.CENT")
    assert iso.source_type is SourceType.ISO_14224
