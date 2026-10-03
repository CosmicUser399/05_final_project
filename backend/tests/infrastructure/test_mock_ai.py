"""Contract tests for MockAIProvider."""

from app.application.ports import ExternalCallStatus
from app.infrastructure.ai.mock_ai import MockAIProvider


def test_mock_ai_equipment_proposal() -> None:
    ai = MockAIProvider()
    result = ai.complete_json(
        system_prompt="x",
        user_prompt=(
            "Установка производства полистирола "
            "мощностью 100 тысяч тонн в год"
        ),
        schema_name="equipment_proposal",
    )
    assert result.status is ExternalCallStatus.SUCCESS
    assert "equipment" in result.content
    assert result.content["brief"]["plant_type"] == "polystyrene_plant"
    assert result.content["brief"]["capacity_value"] == 100000.0
