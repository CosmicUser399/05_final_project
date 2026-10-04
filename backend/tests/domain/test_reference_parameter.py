"""Domain tests for reference parameters and provenance factories."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.provenance import Confidence
from app.domain.provenance import Provenance
from app.domain.provenance import SourceType
from app.domain.reference.entities import ParameterKind
from app.domain.reference.entities import ReferenceParameter


def test_oreda_factory_requires_reference() -> None:
    prov = Provenance.oreda("demo extract table PUMP.CENT / FTF")
    assert prov.source_type is SourceType.OREDA
    assert prov.confidence is Confidence.HIGH
    assert prov.source_reference is not None
    assert prov.generated_at is not None


def test_iso14224_factory() -> None:
    prov = Provenance.iso14224("ISO 14224 demo code PUMP.CENT")
    assert prov.source_type is SourceType.ISO_14224
    assert prov.confidence is Confidence.HIGH


def test_reference_parameter_round_trip_fields() -> None:
    param = ReferenceParameter(
        source_id=uuid4(),
        equipment_class="Centrifugal pump",
        equipment_class_code="PUMP.CENT",
        failure_mode_code="FTF",
        failure_mode_name="Fail to function",
        parameter_name="failure_rate",
        parameter_kind=ParameterKind.FAILURE_RATE,
        value=3.5e-6,
        unit="1/hour",
        distribution_type="EXPONENTIAL",
        distribution_params_json={"lambda": 3.5e-6},
        source_type=SourceType.OREDA,
        source_document="OREDA demo extract (synthetic)",
        source_reference="demo extract table PUMP.CENT / FTF",
        confidence=Confidence.MEDIUM,
    )
    assert param.parameter_kind is ParameterKind.FAILURE_RATE
    assert param.value == pytest.approx(3.5e-6)


def test_blank_equipment_class_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ReferenceParameter(
            source_id=uuid4(),
            equipment_class="  ",
            parameter_name="failure_rate",
            parameter_kind=ParameterKind.FAILURE_RATE,
            value=1.0,
            unit="1/hour",
            source_type=SourceType.OREDA,
            source_document="doc",
            source_reference="ref",
        )
