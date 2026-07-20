from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from croqui_engine.core.models import BBox, SerializableModel, TechnicalPayload
from croqui_engine.output.contract import (
    make_equipment_label,
    normalize_equipment_type,
    output_contract_from_payload,
    output_header_values,
)

EquipmentType = Literal["TR", "FU", "FC", "RL", "RG", "OL", "SC"]
NodeKind = Literal["pole", "equipment", "transformer", "switch", "junction"]
NetworkType = Literal["AT", "BT", "AT_BT", "UNKNOWN"]
EdgeStyle = Literal["solid", "dashed"]
LabelKind = Literal["code", "network", "note", "kva"]
GraphStatus = Literal["draft", "final_candidate", "blocked"]


class CroquiGraphHeader(SerializableModel):
    departamento: str = ""
    municipio: str = ""
    equipamento: str = ""
    data_levantamento: str = ""
    responsavel: str = ""


class CroquiMainEquipment(SerializableModel):
    id: str = ""
    type: EquipmentType | str = ""
    code: str = ""
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class CroquiNode(SerializableModel):
    id: str
    kind: NodeKind = "junction"
    code: str = ""
    equipmentType: EquipmentType | str = ""
    isMain: bool = False
    sourceBbox: list[float] = Field(default_factory=list)
    confidence: float = 0.0
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


class CroquiEdge(SerializableModel):
    id: str
    source: str
    target: str
    networkType: NetworkType = "UNKNOWN"
    style: EdgeStyle = "solid"
    confidence: float = 0.0


class CroquiLabel(SerializableModel):
    id: str
    text: str
    attachedTo: str
    kind: LabelKind = "code"
    x: float | None = None
    y: float | None = None


class CroquiWorkZone(SerializableModel):
    id: str
    kind: Literal["red_dashed_rectangle"] = "red_dashed_rectangle"
    attachedTo: str = ""
    confidence: float = 0.0
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


class CroquiGraphValidation(SerializableModel):
    status: GraphStatus = "draft"
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    blockingErrors: list[dict[str, Any]] = Field(default_factory=list)


class CroquiGraph(SerializableModel):
    id: str
    header: CroquiGraphHeader = Field(default_factory=CroquiGraphHeader)
    mainEquipment: CroquiMainEquipment = Field(default_factory=CroquiMainEquipment)
    nodes: list[CroquiNode] = Field(default_factory=list)
    edges: list[CroquiEdge] = Field(default_factory=list)
    labels: list[CroquiLabel] = Field(default_factory=list)
    workZones: list[CroquiWorkZone] = Field(default_factory=list)
    validation: CroquiGraphValidation = Field(default_factory=CroquiGraphValidation)


def croqui_graph_from_payload(payload: TechnicalPayload) -> CroquiGraph:
    contract = output_contract_from_payload(payload)
    header_values = output_header_values(payload)
    selected_type = normalize_equipment_type(
        contract.selected_equipment_type if contract else payload.meta.get("selected_equipment_type")
    )
    selected_code = str((contract.selected_equipment_code if contract else "") or "")
    main_id = _main_equipment_node_id(payload, selected_type, selected_code)
    nodes = _nodes_from_payload(payload, main_id, selected_code)
    edges = _edges_from_payload(payload, {node.id for node in nodes})
    labels = _labels_from_nodes(nodes)
    work_zones = _work_zones(main_id, contract.selected_equipment_confidence if contract else None)
    validation = _validation_from_contract(contract)
    equipment_label = make_equipment_label(selected_type, selected_code)
    return CroquiGraph(
        id=payload.job_id or "croqui-graph",
        header=CroquiGraphHeader(
            departamento=str(header_values.get("department") or ""),
            municipio=str(header_values.get("municipality") or ""),
            equipamento=equipment_label or str(header_values.get("equipment") or ""),
            data_levantamento=str(header_values.get("survey_date") or ""),
            responsavel=str(header_values.get("surveyor") or ""),
        ),
        mainEquipment=CroquiMainEquipment(
            id=main_id,
            type=selected_type or "",
            code=selected_code,
            confidence=float((contract.selected_equipment_confidence if contract else 0.0) or 0.0),
            evidence=list(contract.selected_equipment_evidence if contract else []),
        ),
        nodes=nodes,
        edges=edges,
        labels=labels,
        workZones=work_zones,
        validation=validation,
    )


def validate_croqui_graph_for_export(graph: CroquiGraph, svg: str) -> CroquiGraphValidation:
    warnings = list(graph.validation.warnings)
    blocking: list[dict[str, Any]] = []
    main = graph.mainEquipment
    expected_label = make_equipment_label(main.type, main.code)
    if not main.id or not main.code or not main.type:
        blocking.append({"code": "MAIN_EQUIPMENT_MISSING"})
    if expected_label and _norm(graph.header.equipamento) != _norm(expected_label):
        blocking.append(
            {
                "code": "HEADER_MAIN_EQUIPMENT_MISMATCH",
                "expected": expected_label,
                "generated": graph.header.equipamento,
            }
        )
    if not graph.nodes:
        blocking.append({"code": "GRAPH_WITHOUT_NODES"})
    if not graph.edges:
        blocking.append({"code": "GRAPH_WITHOUT_EDGES"})
    if main.code and main.code not in svg:
        blocking.append({"code": "SVG_MAIN_EQUIPMENT_NOT_FOUND", "code_value": main.code})
    if "<svg" not in svg.lower() or "</svg>" not in svg.lower():
        blocking.append({"code": "SVG_INVALID_OR_MISSING"})
    # This validator is called only after the engineer explicitly requests a
    # regeneration. Warnings remain visible, but only blocking errors prevent
    # the reviewed graph from becoming the final candidate.
    status: GraphStatus = "blocked" if blocking else "final_candidate"
    return CroquiGraphValidation(
        status=status,
        warnings=_dedupe(warnings),
        blockingErrors=_dedupe([*graph.validation.blockingErrors, *blocking]),
    )


def _nodes_from_payload(
    payload: TechnicalPayload,
    main_id: str,
    selected_code: str,
) -> list[CroquiNode]:
    raw_graph = payload.meta.get("electrical_graph") or {}
    raw_nodes = raw_graph.get("nodes") or []
    if raw_nodes:
        return [_node_from_graph_item(item, main_id, selected_code) for item in raw_nodes]

    nodes: list[CroquiNode] = []
    for node in payload.active_nodes():
        nodes.append(
            CroquiNode(
                id=node.id,
                kind="pole" if (node.type or "").upper() == "POSTE" else "junction",
                code=node.id if node.id.startswith("P") else "",
                sourceBbox=_bbox_list(node.bbox),
                confidence=float(node.confidence or 0.0),
                x=node.x,
                y=node.y,
            )
        )
    for equipment in payload.active_equipment():
        eq_type = normalize_equipment_type(equipment.type) or equipment.type
        node_id = f"EQ-{eq_type}-{equipment.code}"
        nodes.append(
            CroquiNode(
                id=node_id,
                kind=_kind_for_equipment_type(eq_type),
                code=equipment.code,
                equipmentType=eq_type,
                isMain=equipment.code == selected_code or node_id == main_id,
                sourceBbox=_bbox_list(equipment.bbox),
                confidence=float(equipment.confidence or 0.0),
                x=equipment.bbox.center[0] if equipment.bbox else None,
                y=equipment.bbox.center[1] if equipment.bbox else None,
                width=56,
                height=32,
            )
        )
    return nodes


def _node_from_graph_item(item: dict[str, Any], main_id: str, selected_code: str) -> CroquiNode:
    node_type = normalize_equipment_type(str(item.get("type") or "")) or str(item.get("type") or "")
    position = item.get("position_original") or []
    code = str(item.get("code") or "")
    return CroquiNode(
        id=str(item.get("id") or code),
        kind="pole" if node_type == "POSTE" else _kind_for_equipment_type(node_type),
        code=code,
        equipmentType="" if node_type == "POSTE" else node_type,
        isMain=bool((item.get("id") == main_id) or (code and code == selected_code)),
        sourceBbox=_bbox_list(item.get("bbox_original")),
        confidence=float(item.get("confidence") or 0.0),
        x=float(position[0]) if len(position) >= 2 else None,
        y=float(position[1]) if len(position) >= 2 else None,
        width=56 if node_type != "POSTE" else 18,
        height=32 if node_type != "POSTE" else 18,
    )


def _edges_from_payload(payload: TechnicalPayload, node_ids: set[str]) -> list[CroquiEdge]:
    raw_graph = payload.meta.get("electrical_graph") or {}
    raw_edges = raw_graph.get("edges") or []
    if raw_edges:
        return [
            CroquiEdge(
                id=str(edge.get("id") or f'{edge.get("from_node")}-{edge.get("to_node")}'),
                source=str(edge.get("from_node") or ""),
                target=str(edge.get("to_node") or ""),
                networkType=_network_type(str(edge.get("type") or "")),
                style="dashed" if "INFERIDA" in str(edge.get("type") or "") else "solid",
                confidence=float(edge.get("confidence") or 0.0),
            )
            for edge in raw_edges
            if edge.get("from_node") in node_ids and edge.get("to_node") in node_ids
        ]
    return [
        CroquiEdge(
            id=span.id,
            source=span.from_node,
            target=span.to_node,
            networkType=_network_type(f"{span.network_type or ''} {span.cable or ''}"),
            style="solid" if float(span.confidence or 0.0) >= 0.7 else "dashed",
            confidence=float(span.confidence or 0.0),
        )
        for span in payload.active_spans()
    ]


def _labels_from_nodes(nodes: list[CroquiNode]) -> list[CroquiLabel]:
    labels = []
    for node in nodes:
        text = node.code or node.id
        if not text:
            continue
        labels.append(
            CroquiLabel(
                id=f"LBL-{node.id}",
                text=text,
                attachedTo=node.id,
                kind="code",
                x=node.x,
                y=(node.y - 24) if node.y is not None else None,
            )
        )
    return labels


def _work_zones(main_id: str, confidence: float | None) -> list[CroquiWorkZone]:
    if not main_id:
        return []
    return [
        CroquiWorkZone(
            id=f"WZ-{main_id}",
            attachedTo=main_id,
            confidence=float(confidence or 0.0),
            width=130,
            height=76,
        )
    ]


def _main_equipment_node_id(
    payload: TechnicalPayload,
    selected_type: str | None,
    selected_code: str,
) -> str:
    if selected_type and selected_code:
        candidate = f"EQ-{selected_type}-{selected_code}"
        raw_graph = payload.meta.get("electrical_graph") or {}
        if any(node.get("id") == candidate for node in raw_graph.get("nodes") or []):
            return candidate
        return candidate
    raw_graph = payload.meta.get("electrical_graph") or {}
    for node in raw_graph.get("nodes") or []:
        if node.get("code") and node.get("type") != "POSTE":
            return str(node.get("id"))
    return ""


def _validation_from_contract(contract: Any) -> CroquiGraphValidation:
    if contract is None:
        return CroquiGraphValidation(
            status="draft",
            warnings=[{"code": "OUTPUT_CONTRACT_MISSING"}],
        )
    status: GraphStatus = "draft"
    if contract.blocking_errors:
        status = "blocked"
    elif contract.output_status == "final_candidate":
        status = "final_candidate"
    return CroquiGraphValidation(
        status=status,
        warnings=list(contract.warnings or []),
        blockingErrors=list(contract.blocking_errors or []),
    )


def _kind_for_equipment_type(equipment_type: str | None) -> NodeKind:
    eq_type = normalize_equipment_type(equipment_type)
    if eq_type == "TR":
        return "transformer"
    if eq_type in {"FU", "FC", "RL", "RG", "OL", "SC"}:
        return "switch"
    return "equipment"


def _network_type(text: str) -> NetworkType:
    upper = text.upper()
    if "AT_BT" in upper or ("AT" in upper and "BT" in upper):
        return "AT_BT"
    if "BT" in upper:
        return "BT"
    if "AT" in upper or "PRIM" in upper:
        return "AT"
    return "UNKNOWN"


def _bbox_list(value: BBox | dict[str, Any] | None) -> list[float]:
    if value is None:
        return []
    raw = value.as_dict() if isinstance(value, BBox) else value
    try:
        return [
            float(raw["x0"]),
            float(raw["y0"]),
            float(raw["x1"]),
            float(raw["y1"]),
        ]
    except Exception:
        return []


def _norm(value: str) -> str:
    return " ".join(str(value or "").upper().split())


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for item in items:
        key = tuple(sorted((str(k), str(v)) for k, v in item.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output
