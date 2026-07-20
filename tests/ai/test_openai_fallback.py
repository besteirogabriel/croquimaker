from __future__ import annotations

from types import SimpleNamespace

from croqui_engine.ai import openai_croqui_analyzer as analyzer
from croqui_engine.ai.openai_croqui_analyzer import (
    AIExcelPlacementProposal,
    AIMainEquipmentProposal,
    AINodeProposal,
    OpenAIAnalysisResult,
)
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.graph.croqui_graph import (
    CroquiGraph,
    CroquiGraphHeader,
    CroquiMainEquipment,
    CroquiNode,
    _apply_excel_placement_plan,
)
from croqui_engine.output.contract import CroquiOutputContract, attach_output_contract


def _settings(**overrides):
    values = {
        "openai_fallback_enabled": True,
        "openai_fallback_confidence": 0.72,
        "openai_api_key": "backend-only-test-key",
        "openai_model": "test-model",
        "openai_reasoning_effort": "high",
        "openai_timeout_seconds": 10,
        "openai_max_retries": 0,
        "openai_pdf_detail": "high",
        "openai_max_pdf_mb": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _proposal() -> AIExcelPlacementProposal:
    return AIExcelPlacementProposal(
        main_equipment=AIMainEquipmentProposal(
            equipment_type="FU",
            code="000000",
            confidence=0.86,
            rationale="Synthetic fallback decision.",
            evidence=["Synthetic evidence."],
        ),
        nodes=[
            AINodeProposal(id="source", kind="pole", x=100, y=200),
            AINodeProposal(
                id="main-device",
                kind="switch",
                code="000000",
                equipment_type="FU",
                is_main=True,
                x=240,
                y=200,
            ),
        ],
    )


def test_valid_local_result_never_calls_openai(monkeypatch, tmp_path):
    payload = TechnicalPayload(
        job_id="synthetic-valid-local",
        meta={
            "equipment_decision": {
                "strategy": "deterministic_evidence",
                "automatic": True,
                "confidence": 0.91,
                "candidate": {"equipment_type": "FU", "code": "000000"},
            },
            "electrical_graph": {
                "nodes": [{"id": "source"}, {"id": "main-device"}],
                "edges": [{"source": "source", "target": "main-device"}],
            },
        },
    )
    attach_output_contract(
        payload,
        CroquiOutputContract(
            project_id=payload.job_id,
            selected_equipment_type="FU",
            selected_equipment_code="000000",
            selected_equipment_confidence=0.91,
            primary_focus_code="000000",
            focus_confidence=0.9,
            focus_validated=True,
            output_status="final_candidate",
            validation_status="PASSED",
            final_output_allowed=True,
        ),
    )
    monkeypatch.setattr(analyzer, "settings", _settings())

    def unexpected_call(*args, **kwargs):
        raise AssertionError("OpenAI must not run after an authoritative local result")

    monkeypatch.setattr(analyzer, "analyze_project_pdf", unexpected_call)

    returned, escalated = analyzer.run_openai_fallback(payload, tmp_path / "unused.pdf")

    assert returned is payload
    assert escalated is False
    assert payload.meta["ai_backend"]["status"] == "not_needed"


def test_failed_local_validation_escalates_and_records_structured_plan(monkeypatch, tmp_path):
    project = tmp_path / "synthetic.pdf"
    project.write_bytes(b"%PDF-1.4 synthetic")
    payload = TechnicalPayload(meta={"project_numeric_labels": ["000000"]})
    result = OpenAIAnalysisResult(proposal=_proposal(), model="test-model")
    monkeypatch.setattr(analyzer, "settings", _settings())
    monkeypatch.setattr(
        analyzer,
        "openai_fallback_reasons",
        lambda value: ["LOCAL_OUTPUT_VALIDATION_BLOCKED"],
    )
    monkeypatch.setattr(analyzer, "analyze_project_pdf", lambda path, value: result)

    returned, escalated = analyzer.run_openai_fallback(payload, project)

    assert returned is payload
    assert escalated is True
    assert payload.meta["ai_backend"]["status"] == "completed"
    assert payload.meta["openai_analysis"]["main_equipment"]["code"] == "000000"
    assert payload.meta["excel_placement_plan"]["nodes"][1]["is_main"] is True


def test_responses_request_is_backend_only_and_structured(monkeypatch, tmp_path):
    project = tmp_path / "synthetic.pdf"
    project.write_bytes(b"%PDF-1.4 synthetic")
    captured = {}

    class FakeResponses:
        def parse(self, **request):
            captured.update(request)
            return SimpleNamespace(
                output_parsed=_proposal(),
                id="response-test",
                model="test-model",
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            )

    client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(analyzer, "settings", _settings())

    result = analyzer.analyze_project_pdf(project, TechnicalPayload(), client=client)

    assert result.proposal.main_equipment.code == "000000"
    assert captured["store"] is False
    assert captured["text_format"] is AIExcelPlacementProposal
    assert captured["input"][1]["content"][0]["type"] == "input_file"
    assert "backend-only-test-key" not in str(captured)


def test_openai_plan_is_rejected_when_local_revalidation_selects_another_device():
    graph = CroquiGraph(
        id="synthetic-local-selection",
        header=CroquiGraphHeader(equipamento="TR 111111"),
        mainEquipment=CroquiMainEquipment(
            id="local-main",
            type="TR",
            code="111111",
            confidence=0.8,
        ),
        nodes=[
            CroquiNode(
                id="local-main",
                kind="transformer",
                equipmentType="TR",
                code="111111",
                isMain=True,
            )
        ],
    )

    returned = _apply_excel_placement_plan(graph, _proposal())

    assert returned.nodes[0].id == "local-main"
    assert returned.validation.warnings[-1]["code"] == (
        "OPENAI_FALLBACK_REJECTED_BY_LOCAL_REVALIDATION"
    )
