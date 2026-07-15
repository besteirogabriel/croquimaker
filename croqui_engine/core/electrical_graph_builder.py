from __future__ import annotations

import math
from typing import Any

from pydantic import Field

from croqui_engine.core.models import BBox, SerializableModel, TechnicalPayload
from croqui_engine.output.contract import normalize_equipment_code, normalize_equipment_type


class ElectricalGraphNode(SerializableModel):
    id: str
    type: str
    code: str | None = None
    bbox_original: dict[str, float] | None = None
    position_original: tuple[float, float] | None = None
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ElectricalGraphEdge(SerializableModel):
    id: str
    from_node: str
    to_node: str
    type: str = "CONEXAO_INFERIDA"
    geometry_original: list[tuple[float, float]] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ElectricalGraph(SerializableModel):
    nodes: list[ElectricalGraphNode] = Field(default_factory=list)
    edges: list[ElectricalGraphEdge] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    def node_map(self) -> dict[str, ElectricalGraphNode]:
        return {node.id: node for node in self.nodes}


def build_electrical_graph(payload: TechnicalPayload) -> ElectricalGraph:
    nodes: dict[str, ElectricalGraphNode] = {}
    edges: dict[str, ElectricalGraphEdge] = {}
    warnings: list[dict[str, Any]] = []

    label_positions = _label_positions(payload)

    for node in payload.active_nodes():
        position = _node_position(node.x, node.y, node.bbox)
        nodes[node.id] = ElectricalGraphNode(
            id=node.id,
            type=node.type or "POSTE",
            code=node.id if node.id.startswith("P") else None,
            bbox_original=_bbox_dict(node.bbox),
            position_original=position,
            confidence=node.confidence,
            evidence=[{"kind": "payload_node", "source": node.raw_text or node.id}],
        )

    for span in payload.active_spans():
        for node_id in (span.from_node, span.to_node):
            if node_id not in nodes:
                nodes[node_id] = ElectricalGraphNode(
                    id=node_id,
                    type="POSTE",
                    code=node_id if node_id.startswith("P") else None,
                    confidence=max(span.confidence * 0.8, 0.35),
                    evidence=[{"kind": "span_endpoint", "source": span.id}],
                )
        edge_id = span.id or f"{span.from_node}-{span.to_node}"
        edges[edge_id] = ElectricalGraphEdge(
            id=edge_id,
            from_node=span.from_node,
            to_node=span.to_node,
            type=_edge_type(span.network_type, span.cable),
            confidence=span.confidence,
            evidence=[{"kind": "payload_span", "source": span.raw_text or span.id}],
        )

    for equipment in payload.active_equipment():
        code = normalize_equipment_code(equipment.code)
        eq_type = normalize_equipment_type(equipment.type) or equipment.type
        if not code:
            continue
        node_id = f"EQ-{eq_type}-{code}"
        label_position = label_positions.get(code)
        position = _node_position(None, None, equipment.bbox) or label_position
        nodes[node_id] = ElectricalGraphNode(
            id=node_id,
            type=eq_type,
            code=code,
            bbox_original=_bbox_dict(equipment.bbox) or _bbox_around(position, 24),
            position_original=position,
            confidence=equipment.confidence,
            evidence=[
                {
                    "kind": "payload_equipment",
                    "source": equipment.raw_text or f"{eq_type} {code}",
                    "node_id": equipment.node_id,
                }
            ],
        )
        anchor = equipment.node_id if equipment.node_id in nodes else _nearest_pole(nodes, position)
        if anchor:
            edge_id = f"CONN-{anchor}-{node_id}"
            edges[edge_id] = ElectricalGraphEdge(
                id=edge_id,
                from_node=anchor,
                to_node=node_id,
                type="EQUIPAMENTO",
                geometry_original=[point for point in (nodes[anchor].position_original, position) if point],
                confidence=max(0.35, equipment.confidence * 0.8),
                evidence=[{"kind": "equipment_anchor", "source": code}],
            )

    if not edges and len(nodes) > 1:
        _add_nearest_neighbor_edges(nodes, edges)
        warnings.append({"code": "GRAPH_INFERRED_BY_NEAREST_NEIGHBOR"})

    return ElectricalGraph(nodes=list(nodes.values()), edges=list(edges.values()), warnings=warnings)


def _add_nearest_neighbor_edges(
    nodes: dict[str, ElectricalGraphNode],
    edges: dict[str, ElectricalGraphEdge],
) -> None:
    positioned = [node for node in nodes.values() if node.position_original is not None]
    if len(positioned) < 2:
        return
    connected: set[str] = {positioned[0].id}
    remaining: set[str] = {node.id for node in positioned[1:]}
    node_map = {node.id: node for node in positioned}
    while remaining:
        best = None
        for left in connected:
            for right in remaining:
                dist = _distance(node_map[left].position_original, node_map[right].position_original)
                if best is None or dist < best[0]:
                    best = (dist, left, right)
        if best is None:
            break
        _, left, right = best
        edges[f"INF-{left}-{right}"] = ElectricalGraphEdge(
            id=f"INF-{left}-{right}",
            from_node=left,
            to_node=right,
            type="CONEXAO_INFERIDA",
            geometry_original=[
                node_map[left].position_original or (0, 0),
                node_map[right].position_original or (0, 0),
            ],
            confidence=0.28,
            evidence=[{"kind": "nearest_neighbor_inference"}],
        )
        connected.add(right)
        remaining.remove(right)


def _label_positions(payload: TechnicalPayload) -> dict[str, tuple[float, float]]:
    output: dict[str, tuple[float, float]] = {}
    for item in [
        *(payload.meta.get("project_numeric_label_positions") or []),
        *((payload.meta.get("project_vector_trace") or {}).get("labels") or []),
    ]:
        code = normalize_equipment_code(str(item.get("text") or ""))
        if not code or code in output:
            continue
        try:
            output[code] = (float(item.get("x")), float(item.get("y")))
        except Exception:
            continue
    return output


def _nearest_pole(
    nodes: dict[str, ElectricalGraphNode],
    position: tuple[float, float] | None,
) -> str | None:
    if position is None:
        poles = [node for node in nodes.values() if node.type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}]
        return poles[0].id if poles else None
    candidates = [
        node
        for node in nodes.values()
        if node.position_original is not None and node.type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda node: _distance(position, node.position_original)).id


def _node_position(
    x: float | None,
    y: float | None,
    bbox: BBox | None,
) -> tuple[float, float] | None:
    if x is not None and y is not None:
        return float(x), float(y)
    if bbox is not None:
        return bbox.center
    return None


def _edge_type(network_type: str | None, cable: str | None) -> str:
    text = f"{network_type or ''} {cable or ''}".upper()
    if "BT" in text and "AT" in text:
        return "TRECHO_AT_BT"
    if "BT" in text or "SECUND" in text:
        return "TRECHO_BT"
    if "AT" in text or "PRIM" in text:
        return "TRECHO_AT"
    if "RAMAL" in text:
        return "RAMAL"
    return "TRECHO"


def _bbox_dict(bbox: BBox | None) -> dict[str, float] | None:
    if bbox is None:
        return None
    return bbox.as_dict()


def _bbox_around(position: tuple[float, float] | None, size: float) -> dict[str, float] | None:
    if position is None:
        return None
    x, y = position
    return {"x0": x - size, "y0": y - size, "x1": x + size, "y1": y + size}


def _distance(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
) -> float:
    if a is None or b is None:
        return 999999.0
    return math.hypot(a[0] - b[0], a[1] - b[1])
