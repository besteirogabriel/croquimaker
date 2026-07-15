from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import Field

from croqui_engine.core.electrical_graph_builder import (
    ElectricalGraph,
    ElectricalGraphEdge,
    ElectricalGraphNode,
)
from croqui_engine.core.models import SerializableModel


class FocusSubgraph(SerializableModel):
    selected_nodes: list[ElectricalGraphNode] = Field(default_factory=list)
    selected_edges: list[ElectricalGraphEdge] = Field(default_factory=list)
    included_codes: list[str] = Field(default_factory=list)
    excluded_codes: list[str] = Field(default_factory=list)
    focus_confidence: float = 0.0
    focus_node_id: str | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {node.id for node in self.selected_nodes}


def select_focus_subgraph(
    graph: ElectricalGraph,
    selected_equipment_code: str | None,
    *,
    max_hops: int = 2,
    max_nodes: int = 14,
) -> FocusSubgraph:
    nodes = graph.node_map()
    adjacency = _adjacency(graph.edges)
    warnings: list[dict[str, Any]] = []
    focus_node = _focus_node_id(graph.nodes, selected_equipment_code)
    if not focus_node:
        warnings.append({"code": "FOCUS_NODE_NOT_FOUND"})
        return FocusSubgraph(
            selected_nodes=_fallback_nodes(graph.nodes, max_nodes),
            selected_edges=[],
            included_codes=_codes(_fallback_nodes(graph.nodes, max_nodes)),
            excluded_codes=_excluded_codes(graph.nodes, _fallback_nodes(graph.nodes, max_nodes)),
            focus_confidence=0.25,
            warnings=warnings,
        )

    selected_ids = _bfs_neighborhood(focus_node, adjacency, max_hops=max_hops)
    if len(selected_ids) < 3:
        selected_ids.update(_nearest_position_nodes(nodes, nodes.get(focus_node), limit=4))
    selected_ids = _cap_nodes_by_relevance(nodes, selected_ids, focus_node, max_nodes)
    selected_nodes = [nodes[node_id] for node_id in selected_ids if node_id in nodes]
    selected_edges = [
        edge
        for edge in graph.edges
        if edge.from_node in selected_ids and edge.to_node in selected_ids
    ]
    if not selected_edges and len(selected_nodes) > 1:
        warnings.append({"code": "FOCUS_SUBGRAPH_WITHOUT_CONFIRMED_EDGES"})

    included = _codes(selected_nodes)
    excluded = _excluded_codes(graph.nodes, selected_nodes)
    confidence = _confidence(focus_node, selected_nodes, selected_edges, selected_equipment_code)
    return FocusSubgraph(
        selected_nodes=selected_nodes,
        selected_edges=selected_edges,
        included_codes=included,
        excluded_codes=excluded,
        focus_confidence=confidence,
        focus_node_id=focus_node,
        warnings=warnings,
    )


def _focus_node_id(nodes: list[ElectricalGraphNode], code: str | None) -> str | None:
    if code:
        for node in nodes:
            if node.code == code:
                return node.id
    equipment_nodes = [node for node in nodes if node.code and node.type not in {"POSTE", "EQUIPAMENTO_REFERENCIA"}]
    if equipment_nodes:
        return max(equipment_nodes, key=lambda node: node.confidence).id
    return nodes[0].id if nodes else None


def _adjacency(edges: list[ElectricalGraphEdge]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for edge in edges:
        out.setdefault(edge.from_node, set()).add(edge.to_node)
        out.setdefault(edge.to_node, set()).add(edge.from_node)
    return out


def _bfs_neighborhood(
    start: str,
    adjacency: dict[str, set[str]],
    *,
    max_hops: int,
) -> set[str]:
    selected = {start}
    queue = deque([(start, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor in sorted(adjacency.get(node_id, set())):
            if neighbor in selected:
                continue
            selected.add(neighbor)
            queue.append((neighbor, depth + 1))
    return selected


def _nearest_position_nodes(
    nodes: dict[str, ElectricalGraphNode],
    focus: ElectricalGraphNode | None,
    *,
    limit: int,
) -> set[str]:
    if focus is None or focus.position_original is None:
        return set()
    ranked = sorted(
        (
            (
                _distance(focus.position_original, node.position_original),
                node.id,
            )
            for node in nodes.values()
            if node.position_original is not None
        ),
        key=lambda item: item[0],
    )
    return {node_id for _, node_id in ranked[:limit]}


def _cap_nodes_by_relevance(
    nodes: dict[str, ElectricalGraphNode],
    selected_ids: set[str],
    focus_node: str,
    max_nodes: int,
) -> set[str]:
    if len(selected_ids) <= max_nodes:
        return selected_ids
    focus = nodes.get(focus_node)
    ranked = sorted(
        selected_ids,
        key=lambda node_id: (
            0 if node_id == focus_node else 1,
            _distance(
                focus.position_original if focus else None,
                nodes[node_id].position_original if node_id in nodes else None,
            ),
            -nodes[node_id].confidence if node_id in nodes else 0,
        ),
    )
    return set(ranked[:max_nodes])


def _fallback_nodes(nodes: list[ElectricalGraphNode], max_nodes: int) -> list[ElectricalGraphNode]:
    return sorted(nodes, key=lambda node: (-node.confidence, node.id))[:max_nodes]


def _codes(nodes: list[ElectricalGraphNode]) -> list[str]:
    return sorted({node.code for node in nodes if node.code and node.code.isdigit()})


def _excluded_codes(
    all_nodes: list[ElectricalGraphNode],
    selected_nodes: list[ElectricalGraphNode],
) -> list[str]:
    selected_ids = {node.id for node in selected_nodes}
    return sorted(
        {
            node.code
            for node in all_nodes
            if node.id not in selected_ids and node.code and node.code.isdigit()
        }
    )


def _confidence(
    focus_node: str,
    selected_nodes: list[ElectricalGraphNode],
    selected_edges: list[ElectricalGraphEdge],
    selected_code: str | None,
) -> float:
    if not selected_nodes:
        return 0.0
    node_map = {node.id: node for node in selected_nodes}
    focus = node_map.get(focus_node)
    score = 0.25
    if focus and focus.code == selected_code:
        score += 0.25
    if focus and focus.position_original:
        score += 0.12
    if len(selected_nodes) >= 3:
        score += 0.12
    if selected_edges:
        score += min(0.18, len(selected_edges) * 0.04)
    avg_conf = sum(node.confidence for node in selected_nodes) / len(selected_nodes)
    score += min(0.10, avg_conf * 0.10)
    return round(max(0.0, min(score, 0.98)), 4)


def _distance(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
) -> float:
    if a is None or b is None:
        return 999999.0
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
