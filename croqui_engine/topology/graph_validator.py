from __future__ import annotations

from statistics import mean

from croqui_engine.core.models import TechnicalPayload, ValidationMessage

SYSTEM_VALIDATION_CODES = {
    "PROJECT_PAGE_MISSING",
    "TOPOLOGY_FALLBACK_FROM_EQUIPMENT",
    "CROQUI_RESUMIDO_MISSING",
    "SPAN_WITHOUT_ENDPOINT",
    "SPAN_NODE_MISSING",
    "SPAN_WITHOUT_LENGTH",
    "SPAN_WITHOUT_CABLE",
    "EQUIPMENT_WITHOUT_NODE",
    "EQUIPMENT_NODE_MISSING",
    "TES_TRANSFORMER_NOT_IN_PAYLOAD",
    "MAIN_SWITCHING_EQUIPMENT_NOT_FOUND",
    "LOW_GLOBAL_CONFIDENCE",
}


def validate_graph(payload: TechnicalPayload) -> TechnicalPayload:
    validations: list[ValidationMessage] = [
        item for item in payload.validations if item.code not in SYSTEM_VALIDATION_CODES
    ]
    node_ids = {node.id for node in payload.active_nodes()}

    has_project_page = any(page.kind == "PROJETO_REDE" for page in payload.pages)
    has_croqui_or_evidence = any(page.kind == "CROQUI_RESUMIDO" for page in payload.pages) or bool(
        payload.active_equipment() or payload.active_nodes() or payload.active_spans()
    )
    if not has_project_page:
        validations.append(
            ValidationMessage(
                severity="warning" if has_croqui_or_evidence else "error",
                code="PROJECT_PAGE_MISSING",
                message="Nenhuma pagina de projeto de rede foi identificada com confianca; a saida foi gerada em modo revisavel.",
                suggested_action="Revisar classificacao de paginas e confirmar se existe folha de projeto no PDF.",
            )
        )

    has_reference_spans = any(
        span.status == "referencia" or span.network_type == "REFERENCIA_REVISAO"
        for span in payload.active_spans()
    )
    if (not payload.active_spans() and payload.active_equipment()) or has_reference_spans:
        validations.append(
            ValidationMessage(
                severity="warning",
                code="TOPOLOGY_FALLBACK_FROM_EQUIPMENT",
                message="Nenhum vao confirmado foi extraido; croqui gerado como referencia a partir dos equipamentos/TES.",
                suggested_action="Confirmar manualmente a topologia antes de usar como croqui final.",
            )
        )

    if not any(page.kind == "CROQUI_RESUMIDO" for page in payload.pages):
        validations.append(
            ValidationMessage(
                severity="warning",
                code="CROQUI_RESUMIDO_MISSING",
                message="Croqui resumido nao identificado automaticamente.",
                suggested_action="Prosseguir com revisao humana antes da geracao final.",
            )
        )

    for span in payload.active_spans():
        is_reference_span = span.status == "referencia" or span.network_type == "REFERENCIA_REVISAO"
        if not span.from_node or not span.to_node:
            validations.append(
                ValidationMessage(
                    severity="error",
                    code="SPAN_WITHOUT_ENDPOINT",
                    message=f"Vao {span.id} esta sem origem ou destino.",
                    object_type="span",
                    object_id=span.id,
                )
            )
        for node_id in (span.from_node, span.to_node):
            if node_id not in node_ids:
                validations.append(
                    ValidationMessage(
                        severity="error",
                        code="SPAN_NODE_MISSING",
                        message=f"Vao {span.id} referencia {node_id}, mas o poste nao existe.",
                        object_type="span",
                        object_id=span.id,
                    )
                )
        if span.length_m is None and not is_reference_span:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="SPAN_WITHOUT_LENGTH",
                    message=f"Vao {span.id} nao possui comprimento identificado.",
                    object_type="span",
                    object_id=span.id,
                    suggested_action="Corrigir comprimento na revisao.",
                )
            )
        if not span.cable and not is_reference_span:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="SPAN_WITHOUT_CABLE",
                    message=f"Vao {span.id} nao possui cabo identificado.",
                    object_type="span",
                    object_id=span.id,
                    suggested_action="Conferir anotacao do vao no PDF.",
                )
            )

    for equipment in payload.active_equipment():
        if not equipment.node_id:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="EQUIPMENT_WITHOUT_NODE",
                    message=f"{equipment.type} {equipment.code} foi identificado sem associacao segura a poste.",
                    object_type="equipment",
                    object_id=equipment.code,
                    suggested_action="Associar manualmente ao poste correto na revisao.",
                )
            )
        elif equipment.node_id not in node_ids:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="EQUIPMENT_NODE_MISSING",
                    message=f"{equipment.type} {equipment.code} referencia {equipment.node_id}, nao encontrado.",
                    object_type="equipment",
                    object_id=equipment.code,
                    suggested_action="Corrigir associacao do equipamento.",
                )
            )

    tes_actions = payload.meta.get("tes_actions") or []
    installed_trs = [a for a in tes_actions if a.get("type") == "TRANSFORMADOR" and a.get("status") == "instalar"]
    equipment_codes = {item.code for item in payload.active_equipment()}
    for action in installed_trs:
        if action.get("code") not in equipment_codes:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="TES_TRANSFORMER_NOT_IN_PAYLOAD",
                    message=f"TR {action.get('code')} aparece na TES, mas nao foi confirmado no projeto.",
                    object_type="equipment",
                    object_id=action.get("code"),
                    suggested_action="Validar no PDF e manter se a TES estiver correta.",
                )
            )

    main_equipment = payload.meta.get("main_switching_equipment")
    if main_equipment:
        found = any(item.code in str(main_equipment) for item in payload.active_equipment())
        if not found:
            validations.append(
                ValidationMessage(
                    severity="warning",
                    code="MAIN_SWITCHING_EQUIPMENT_NOT_FOUND",
                    message=f"Equipamento principal de manobra '{main_equipment}' nao foi associado no projeto.",
                    suggested_action="Conferir plano de manobra e folha de projeto.",
                )
            )

    payload.validations = _dedupe_validations(validations)
    payload.confidence_global = calculate_confidence(payload)
    if payload.confidence_global < 0.7:
        payload.validations.append(
            ValidationMessage(
                severity="warning",
                code="LOW_GLOBAL_CONFIDENCE",
                message=f"Confianca global {payload.confidence_global:.2f} exige revisao humana.",
                suggested_action="Revisar itens marcados antes de aprovar.",
            )
        )
    return payload


def calculate_confidence(payload: TechnicalPayload) -> float:
    tes_score = 0.9 if payload.meta.get("tes_number") else 0.35
    equipment_score = _avg([item.confidence for item in payload.active_equipment()])
    span_score = _avg([item.confidence for item in payload.active_spans()])
    node_score = _avg([item.confidence for item in payload.active_nodes()])
    associated = [item for item in payload.active_equipment() if item.node_id]
    association_score = len(associated) / len(payload.active_equipment()) if payload.active_equipment() else 0.35

    score = (
        tes_score * 0.15
        + equipment_score * 0.25
        + span_score * 0.25
        + node_score * 0.20
        + association_score * 0.15
    )
    return round(max(0.0, min(1.0, score)), 3)


def _avg(values: list[float]) -> float:
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else 0.35


def _dedupe_validations(items: list[ValidationMessage]) -> list[ValidationMessage]:
    seen: set[tuple[str, str | None, str]] = set()
    out: list[ValidationMessage] = []
    for item in items:
        key = (item.code, item.object_id, item.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
