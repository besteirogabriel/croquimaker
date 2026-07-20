from __future__ import annotations

from pathlib import Path

from pydantic import Field

from croqui_engine.core.equipment_candidate_resolver import (
    EquipmentCandidate,
    EquipmentCandidateEvidence,
    resolve_equipment_candidates,
)
from croqui_engine.core.models import SerializableModel, TechnicalPayload
from croqui_engine.corpus.matcher import find_project_match
from croqui_engine.output.contract import (
    make_equipment_label,
    normalize_equipment_code,
    normalize_equipment_type,
)


class EquipmentDecision(SerializableModel):
    candidate: EquipmentCandidate | None = None
    strategy: str = "unresolved"
    automatic: bool = False
    confidence: float = 0.0
    alternatives: list[EquipmentCandidate] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


PROTECTIVE_TYPES = {"FU", "FC", "RL", "RG", "OL", "SC"}


def decide_main_equipment(
    payload: TechnicalPayload, source_pdf_path: Path | None = None
) -> EquipmentDecision:
    """Choose the operational isolation device before rendering.

    An exact approved corpus match is authoritative. For unseen projects, protective
    devices outrank transformers when supported by switching/topology evidence. The
    execution-plan transformer alone is never promoted over a plausible upstream
    isolation device.
    """
    if source_pdf_path:
        match = find_project_match(source_pdf_path)
        eq_type = normalize_equipment_type(match.equipment_type if match else "")
        code = normalize_equipment_code(match.equipment_code if match else "")
        if match and eq_type and code:
            candidate = EquipmentCandidate(
                equipment_type=eq_type,
                code=code,
                label=make_equipment_label(eq_type, code),
                confidence=1.0,
                source="approved_corpus",
                evidence=[
                    EquipmentCandidateEvidence(
                        kind="approved_corpus",
                        weight=1.0,
                        source=match.case_id,
                        detail=match.project_pdf_name,
                    )
                ],
            )
            return EquipmentDecision(
                candidate=candidate, strategy="approved_corpus", automatic=True, confidence=1.0
            )

    candidates = resolve_equipment_candidates(payload, source_pdf_path=source_pdf_path)
    ai_candidate = _openai_candidate(payload, candidates)
    if ai_candidate:
        candidates = [
            item
            for item in candidates
            if not (
                item.equipment_type == ai_candidate.equipment_type
                and item.code == ai_candidate.code
            )
        ]
        candidates.append(ai_candidate)
    if not candidates:
        return EquipmentDecision(warnings=[{"code": "NO_EQUIPMENT_CANDIDATE"}])

    ranked = sorted(candidates, key=_decision_score, reverse=True)
    selected = ranked[0]
    score = _decision_score(selected)
    gap = score - (_decision_score(ranked[1]) if len(ranked) > 1 else 0.0)
    automatic = score >= 0.62 and gap >= 0.08
    warnings = []
    if selected.source == "openai_pdf_analysis" and not _openai_corroborated(payload):
        warnings.append({"code": "OPENAI_DECISION_NOT_CORROBORATED_LOCALLY"})
        automatic = False
    if selected.equipment_type == "TR" and any(
        item.equipment_type in PROTECTIVE_TYPES for item in ranked[1:]
    ):
        warnings.append({"code": "TRANSFORMER_SELECTED_WITH_PROTECTIVE_ALTERNATIVE"})
        automatic = False
    if not automatic:
        warnings.append(
            {
                "code": "DECISION_REQUIRES_ENGINEER_REVIEW",
                "score": round(score, 4),
                "gap": round(gap, 4),
            }
        )
    selected.confidence = round(min(score, 0.99), 4)
    return EquipmentDecision(
        candidate=selected,
        strategy=(
            "openai_pdf_analysis"
            if selected.source == "openai_pdf_analysis"
            else "deterministic_evidence"
        ),
        automatic=automatic,
        confidence=selected.confidence,
        alternatives=ranked[1:6],
        warnings=warnings,
    )


def _decision_score(candidate: EquipmentCandidate) -> float:
    score = float(candidate.confidence or 0.0)
    kinds = {item.kind for item in candidate.evidence}
    if candidate.equipment_type in PROTECTIVE_TYPES:
        score += 0.16
    if "execution_plan" in kinds and candidate.equipment_type in PROTECTIVE_TYPES:
        score += 0.12
    if "near_work_zone" in kinds or "topology_position" in kinds:
        score += 0.08
    if candidate.equipment_type == "TR" and kinds <= {"execution_plan", "equipment_table"}:
        score -= 0.18
    return max(0.0, min(score, 0.99))


def _openai_candidate(
    payload: TechnicalPayload,
    local_candidates: list[EquipmentCandidate],
) -> EquipmentCandidate | None:
    analysis = payload.meta.get("openai_analysis") or {}
    main = analysis.get("main_equipment") or {}
    eq_type = normalize_equipment_type(str(main.get("equipment_type") or ""))
    code = normalize_equipment_code(str(main.get("code") or ""))
    if not eq_type or not code:
        return None
    ai_confidence = max(0.0, min(float(main.get("confidence") or 0.0), 1.0))
    local = next(
        (
            item
            for item in local_candidates
            if item.equipment_type == eq_type and item.code == code
        ),
        None,
    )
    corroborated = bool(main.get("locally_corroborated"))
    confidence = ai_confidence
    evidence = [
        EquipmentCandidateEvidence(
            kind="openai_pdf_analysis",
            weight=round(max(ai_confidence, 0.01), 4),
            source=str((payload.meta.get("ai_backend") or {}).get("model") or "openai"),
            detail=str(main.get("rationale") or "Analise visual e semantica do PDF."),
        )
    ]
    for detail in main.get("evidence") or []:
        evidence.append(
            EquipmentCandidateEvidence(
                kind="openai_visual_evidence",
                weight=0.08,
                source="structured_pdf_analysis",
                detail=str(detail),
            )
        )
    if local:
        evidence.extend(local.evidence)
        confidence = min(0.99, ai_confidence * 0.72 + local.confidence * 0.28 + 0.05)
    elif corroborated:
        confidence = min(0.99, ai_confidence + 0.05)
    return EquipmentCandidate(
        equipment_type=eq_type,
        code=code,
        label=make_equipment_label(eq_type, code),
        confidence=round(confidence, 4),
        evidence=evidence,
        bbox=local.bbox if local else None,
        source="openai_pdf_analysis",
    )


def _openai_corroborated(payload: TechnicalPayload) -> bool:
    main = (payload.meta.get("openai_analysis") or {}).get("main_equipment") or {}
    return bool(main.get("locally_corroborated"))
