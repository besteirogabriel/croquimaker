from croqui_engine.benchmark.metrics import acceptance_level
from croqui_engine.benchmark.technical_metrics import compare_technical
from croqui_engine.core.models import Equipment, TechnicalPayload
from croqui_engine.corpus.models import GoldenCase


def test_acceptance_level_blocks_failed_or_missing_equipment():
    assert acceptance_level(0.99, 0.99, 1.0, ok=False) == "BLOCKED"
    assert acceptance_level(0.99, 0.99, 0.49, ok=True) == "BLOCKED"


def test_acceptance_level_approves_high_combined_score():
    assert acceptance_level(0.96, 0.95, 1.0, ok=True) == "APPROVED"


def test_compare_technical_scores_expected_equipment_from_case_name():
    case = GoldenCase(
        case_id="case-001",
        directory=".",
        equipment_type_from_name="TR",
        equipment_code_from_name="123456",
    )
    payload = TechnicalPayload(
        equipment=[Equipment(code="123456", type="TRANSFORMADOR", confidence=0.95)]
    )

    metrics = compare_technical(case, payload)

    assert metrics["equipment_score"] == 1.0
    assert metrics["type_ok"] is True
    assert metrics["code_ok"] is True
