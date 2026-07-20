from __future__ import annotations

from types import SimpleNamespace

from croqui_engine.core import decision_engine
from croqui_engine.core.decision_engine import decide_main_equipment
from croqui_engine.core.equipment_candidate_resolver import (
    EquipmentCandidate,
    EquipmentCandidateEvidence,
)
from croqui_engine.core.models import TechnicalPayload


def _candidate(
    equipment_type: str, code: str, confidence: float, kinds: list[str]
) -> EquipmentCandidate:
    return EquipmentCandidate(
        equipment_type=equipment_type,
        code=code,
        label=f"{equipment_type} {code}",
        confidence=confidence,
        source=kinds[0],
        evidence=[
            EquipmentCandidateEvidence(kind=kind, weight=0.2, source="test") for kind in kinds
        ],
    )


def test_approved_corpus_equipment_is_authoritative(monkeypatch, tmp_path):
    project = tmp_path / "projeto.pdf"
    project.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        decision_engine,
        "find_project_match",
        lambda path: SimpleNamespace(
            case_id="case-rl",
            project_pdf_name=path.name,
            equipment_type="RL",
            equipment_code="1007569",
        ),
    )

    decision = decide_main_equipment(TechnicalPayload(), project)

    assert decision.candidate is not None
    assert decision.candidate.label == "RL 1007569"
    assert decision.strategy == "approved_corpus"
    assert decision.automatic is True


def test_protective_device_outranks_execution_transformer(monkeypatch):
    transformer = _candidate("TR", "1291393", 0.72, ["execution_plan", "equipment_table"])
    fuse = _candidate("FU", "1130054", 0.56, ["execution_plan", "topology_position"])
    monkeypatch.setattr(
        decision_engine,
        "resolve_equipment_candidates",
        lambda payload, source_pdf_path=None: [transformer, fuse],
    )

    decision = decide_main_equipment(TechnicalPayload())

    assert decision.candidate is not None
    assert decision.candidate.label == "FU 1130054"
    assert decision.strategy == "deterministic_evidence"
