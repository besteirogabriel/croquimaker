from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from croqui_engine.core.config import settings
from croqui_engine.core.models import Equipment, SerializableModel, TechnicalPayload
from croqui_engine.output.contract import (
    normalize_equipment_code,
    normalize_equipment_type,
    output_contract_from_payload,
)

EquipmentType = Literal["TR", "FU", "FC", "RL", "RG", "OL", "SC"]
NodeKind = Literal["pole", "equipment", "transformer", "switch", "junction"]
NetworkType = Literal["AT", "BT", "AT_BT", "UNKNOWN"]


class AIConfigurationError(RuntimeError):
    """The optional OpenAI fallback cannot run safely."""


class AIAnalysisError(RuntimeError):
    """The fallback did not produce a usable technical proposal."""


class AIHeaderProposal(SerializableModel):
    departamento: str = ""
    municipio: str = ""
    data_levantamento: str = ""
    responsavel: str = ""


class AIMainEquipmentProposal(SerializableModel):
    equipment_type: EquipmentType
    code: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence: list[str] = Field(default_factory=list)


class AINodeProposal(SerializableModel):
    id: str
    kind: NodeKind
    code: str = ""
    equipment_type: EquipmentType | str = ""
    is_main: bool = False
    x: float
    y: float
    width: float = 42.0
    height: float = 42.0
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class AIEdgeProposal(SerializableModel):
    id: str
    source: str
    target: str
    network_type: NetworkType = "UNKNOWN"
    style: Literal["solid", "dashed"] = "solid"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class AILabelProposal(SerializableModel):
    id: str
    text: str
    attached_to: str
    kind: Literal["code", "network", "note", "kva"] = "code"
    x: float | None = None
    y: float | None = None


class AIWorkZoneProposal(SerializableModel):
    id: str
    attached_to: str
    x: float
    y: float
    width: float = 64.0
    height: float = 54.0
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class AIExcelPlacementProposal(SerializableModel):
    """Logical placements that are converted into official Excel objects."""

    header: AIHeaderProposal = Field(default_factory=AIHeaderProposal)
    main_equipment: AIMainEquipmentProposal
    nodes: list[AINodeProposal] = Field(default_factory=list)
    edges: list[AIEdgeProposal] = Field(default_factory=list)
    labels: list[AILabelProposal] = Field(default_factory=list)
    work_zones: list[AIWorkZoneProposal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OpenAIAnalysisResult(SerializableModel):
    proposal: AIExcelPlacementProposal
    response_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


SYSTEM_PROMPT = """Você é o fallback técnico de um engine local de croquis de isolamento.
Você só é chamado quando a decisão ou validação local ficou incompleta ou ambígua.
Analise o PDF e a extração local, corrija a decisão e devolva um plano lógico de posicionamento.

Regras obrigatórias:
1. Identifique o dispositivo que realmente nomeia e define o isolamento do croqui. Não presuma que o
   primeiro equipamento da tabela de manobras seja esse dispositivo.
2. Tipos válidos: TR (transformador), FU (chave fusível), FC (chave de comando), RL (religador),
   RG (regulador), OL (chave a óleo) e SC (seccionalizador).
3. Considere plano de execução, ações abrir/fechar/instalar/retirar, marcações da área de trabalho,
   posição elétrica, rede a montante e a jusante, códigos próximos e símbolos do projeto.
4. Dispositivos de proteção/manobra só têm prioridade sobre o transformador quando houver evidência.
   Se a intervenção e o isolamento forem no transformador e não houver dispositivo externo comprovado,
   selecione TR.
5. Nunca invente códigos. Em ambiguidade, reduza a confiança e registre warnings para o engenheiro.
6. Produza objetos e ligações para uma área de desenho aproximada x=80..760 e y=150..540.
7. Não desenhe ícones. O backend copiará os objetos oficiais da aba Simbologia do Excel.
8. O equipamento principal deve existir como nó is_main=true e estar ligado ao trecho.
"""


def run_openai_fallback(
    payload: TechnicalPayload,
    pdf_path: Path,
) -> tuple[TechnicalPayload, bool]:
    reasons = openai_fallback_reasons(payload)
    if not reasons:
        payload.meta["ai_backend"] = {
            "status": "not_needed",
            "provider": "local_engine",
        }
        return payload, False
    if not settings.openai_fallback_enabled:
        payload.meta["ai_backend"] = {
            "status": "disabled",
            "provider": "local_engine",
            "escalation_reasons": reasons,
        }
        return payload, False
    if not settings.openai_api_key:
        payload.meta["ai_backend"] = {
            "status": "not_configured",
            "provider": "local_engine",
            "escalation_reasons": reasons,
        }
        return payload, False
    try:
        result = analyze_project_pdf(pdf_path, payload)
        payload = apply_openai_result(payload, result, escalation_reasons=reasons)
    except (AIConfigurationError, AIAnalysisError) as exc:
        payload.meta["ai_backend"] = {
            "status": "failed",
            "provider": "openai",
            "error_type": type(exc).__name__,
            "escalation_reasons": reasons,
        }
        return payload, False
    return payload, True


def openai_fallback_reasons(payload: TechnicalPayload) -> list[str]:
    decision = payload.meta.get("equipment_decision") or {}
    reasons: list[str] = []
    candidate = decision.get("candidate") or {}
    if not candidate.get("code") or not candidate.get("equipment_type"):
        reasons.append("LOCAL_MAIN_EQUIPMENT_UNRESOLVED")
    if not decision.get("automatic"):
        reasons.append("LOCAL_DECISION_AMBIGUOUS")
    if float(decision.get("confidence") or 0.0) < settings.openai_fallback_confidence:
        reasons.append("LOCAL_DECISION_LOW_CONFIDENCE")
    contract = output_contract_from_payload(payload)
    if contract is None:
        reasons.append("LOCAL_OUTPUT_CONTRACT_MISSING")
    else:
        if contract.blocking_errors:
            reasons.append("LOCAL_OUTPUT_VALIDATION_BLOCKED")
        if not contract.focus_validated:
            reasons.append("LOCAL_FOCUS_NOT_VALIDATED")
    electrical_graph = payload.meta.get("electrical_graph") or {}
    if not electrical_graph.get("nodes") or not electrical_graph.get("edges"):
        reasons.append("LOCAL_TOPOLOGY_INCOMPLETE")
    return list(dict.fromkeys(reasons))


def analyze_project_pdf(
    pdf_path: Path,
    payload: TechnicalPayload,
    *,
    client=None,
) -> OpenAIAnalysisResult:
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if size_mb > settings.openai_max_pdf_mb:
        raise AIConfigurationError(
            f"PDF com {size_mb:.1f} MB excede OPENAI_MAX_PDF_MB={settings.openai_max_pdf_mb}."
        )
    client = client or _openai_client()
    file_data = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    request: dict = {
        "model": settings.openai_model,
        "store": False,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": pdf_path.name,
                        "file_data": f"data:application/pdf;base64,{file_data}",
                        "detail": _pdf_detail(),
                    },
                    {"type": "input_text", "text": _technical_context(payload)},
                ],
            },
        ],
        "text_format": AIExcelPlacementProposal,
    }
    if settings.openai_reasoning_effort in {"low", "medium", "high", "xhigh"}:
        request["reasoning"] = {"effort": settings.openai_reasoning_effort}
    try:
        response = client.responses.parse(**request)
    except Exception as exc:
        raise AIAnalysisError(f"Falha na analise OpenAI ({type(exc).__name__}).") from exc
    proposal = getattr(response, "output_parsed", None)
    if proposal is None:
        raise AIAnalysisError("A OpenAI nao retornou um plano Excel estruturado.")
    if not isinstance(proposal, AIExcelPlacementProposal):
        proposal = AIExcelPlacementProposal.model_validate(proposal)
    usage = getattr(response, "usage", None)
    return OpenAIAnalysisResult(
        proposal=proposal,
        response_id=str(getattr(response, "id", "") or ""),
        model=str(getattr(response, "model", "") or settings.openai_model),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )


def apply_openai_result(
    payload: TechnicalPayload,
    result: OpenAIAnalysisResult,
    *,
    escalation_reasons: list[str],
) -> TechnicalPayload:
    proposal = result.proposal
    eq_type = normalize_equipment_type(proposal.main_equipment.equipment_type)
    code = normalize_equipment_code(proposal.main_equipment.code)
    if not eq_type or not code:
        raise AIAnalysisError("A decisao OpenAI nao trouxe tipo/codigo validos.")
    corroborated = _locally_corroborated(payload, eq_type, code)
    payload.meta["ai_backend"] = {
        "status": "completed",
        "provider": "openai_fallback",
        "model": result.model,
        "response_id": result.response_id,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "escalation_reasons": escalation_reasons,
    }
    payload.meta["openai_analysis"] = {
        "main_equipment": {
            "equipment_type": eq_type,
            "code": code,
            "confidence": proposal.main_equipment.confidence,
            "rationale": proposal.main_equipment.rationale,
            "evidence": proposal.main_equipment.evidence,
            "locally_corroborated": corroborated,
        },
        "warnings": proposal.warnings,
    }
    payload.meta["excel_placement_plan"] = proposal.as_dict()
    _apply_header(payload, proposal.header)
    if not any(
        normalize_equipment_type(item.type) == eq_type
        and normalize_equipment_code(item.code) == code
        for item in payload.active_equipment()
    ):
        main_node = next((node for node in proposal.nodes if node.is_main), None)
        payload.equipment.append(
            Equipment(
                code=code,
                type=eq_type,
                confidence=proposal.main_equipment.confidence,
                raw_text="OpenAI fallback analysis",
                node_id=main_node.id if main_node else None,
            )
        )
    return payload


def ai_backend_status() -> dict[str, str | bool]:
    return {
        "mode": "local_first_openai_fallback",
        "enabled": settings.openai_fallback_enabled,
        "configured": bool(settings.openai_api_key),
        "model": settings.openai_model,
        "provider": "openai",
    }


def _openai_client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIConfigurationError("Pacote openai nao instalado no backend.") from exc
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )


def _technical_context(payload: TechnicalPayload) -> str:
    context = {
        "instruction": (
            "A extracao local falhou em um ou mais criterios. Corrija usando o PDF sem inventar dados."
        ),
        "local_failure_reasons": openai_fallback_reasons(payload),
        "metadata": {
            key: payload.meta.get(key)
            for key in (
                "municipality",
                "department",
                "survey_date",
                "surveyor",
                "tes_actions",
                "project_numeric_labels",
                "project_numeric_label_positions",
                "equipment_decision",
            )
            if payload.meta.get(key)
        },
        "equipment": [item.as_dict() for item in payload.active_equipment()[:100]],
        "nodes": [item.as_dict() for item in payload.active_nodes()[:250]],
        "spans": [item.as_dict() for item in payload.active_spans()[:300]],
        "work_areas": [item.as_dict() for item in payload.work_areas[:50]],
    }
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:60000]


def _locally_corroborated(payload: TechnicalPayload, eq_type: str, code: str) -> bool:
    if any(
        normalize_equipment_type(item.type) == eq_type
        and normalize_equipment_code(item.code) == code
        for item in payload.active_equipment()
    ):
        return True
    labels = {
        normalize_equipment_code(str(item))
        for item in payload.meta.get("project_numeric_labels") or []
    }
    if code in labels:
        return True
    return any(
        normalize_equipment_code(str(action.get("code") or "")) == code
        and normalize_equipment_type(str(action.get("label") or action.get("type") or ""))
        == eq_type
        for action in payload.meta.get("tes_actions") or []
    )


def _apply_header(payload: TechnicalPayload, header: AIHeaderProposal) -> None:
    for key, value in {
        "department": header.departamento,
        "municipality": header.municipio,
        "survey_date": header.data_levantamento,
        "surveyor": header.responsavel,
    }.items():
        if value:
            payload.meta[key] = value


def _pdf_detail() -> str:
    if settings.openai_pdf_detail in {"auto", "low", "high"}:
        return settings.openai_pdf_detail
    return "high"
