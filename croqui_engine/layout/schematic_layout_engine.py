from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import Field

from croqui_engine.core.electrical_graph_builder import ElectricalGraphEdge, ElectricalGraphNode
from croqui_engine.core.focus_subgraph_selector import FocusSubgraph
from croqui_engine.core.models import SerializableModel

SCHEMATIC_CANVAS = {"width": 1000.0, "height": 420.0}


class SchematicNode(SerializableModel):
    id: str
    source_id: str
    type: str
    code: str | None = None
    x: float
    y: float
    is_focus: bool = False


class SchematicEdge(SerializableModel):
    id: str
    from_node: str
    to_node: str
    type: str
    points: list[tuple[float, float]] = Field(default_factory=list)


class SchematicLabel(SerializableModel):
    text: str
    x: float
    y: float
    target_id: str
    role: str = "label"
    min_font_size: float = 13.0


class SchematicSymbol(SerializableModel):
    kind: str
    code: str | None
    node_id: str
    x: float
    y: float
    label: str | None = None


class SchematicWorkZone(SerializableModel):
    x: float
    y: float
    width: float
    height: float
    angle: float = -12.0


class SchematicLayout(SerializableModel):
    schema_version: str = "schematic-layout-v1"
    source: str = "SchematicLayoutEngine"
    canvas: dict[str, float] = Field(default_factory=lambda: dict(SCHEMATIC_CANVAS))
    nodes: list[SchematicNode] = Field(default_factory=list)
    edges: list[SchematicEdge] = Field(default_factory=list)
    labels: list[SchematicLabel] = Field(default_factory=list)
    symbols: list[SchematicSymbol] = Field(default_factory=list)
    work_zones: list[SchematicWorkZone] = Field(default_factory=list)
    included_codes: list[str] = Field(default_factory=list)
    excluded_codes: list[str] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


def build_schematic_layout(
    subgraph: FocusSubgraph,
    *,
    selected_equipment_code: str | None,
) -> SchematicLayout:
    nodes = {node.id: node for node in subgraph.selected_nodes}
    edges = subgraph.selected_edges
    adjacency = _adjacency(edges)
    focus_id = subgraph.focus_node_id or _focus_node_id(subgraph.selected_nodes, selected_equipment_code)
    warnings = list(subgraph.warnings)
    if not nodes:
        return SchematicLayout(warnings=[{"code": "SCHEMATIC_EMPTY_GRAPH"}])

    trunk = _trunk_path(nodes, adjacency, focus_id)
    coordinates = _assign_coordinates(nodes, adjacency, trunk, focus_id)
    schematic_nodes = [
        SchematicNode(
            id=node_id,
            source_id=node_id,
            type=nodes[node_id].type,
            code=nodes[node_id].code,
            x=round(point[0], 2),
            y=round(point[1], 2),
            is_focus=(node_id == focus_id or nodes[node_id].code == selected_equipment_code),
        )
        for node_id, point in coordinates.items()
        if node_id in nodes
    ]
    schematic_edges = [
        _schematic_edge(edge, coordinates)
        for edge in edges
        if edge.from_node in coordinates and edge.to_node in coordinates
    ]
    labels = _labels(schematic_nodes)
    symbols = _symbols(schematic_nodes)
    work_zones = _work_zones(schematic_nodes, selected_equipment_code, focus_id)
    if len(schematic_edges) == 0 and len(schematic_nodes) > 1:
        warnings.append({"code": "SCHEMATIC_LAYOUT_WITHOUT_EDGES"})
    return SchematicLayout(
        nodes=schematic_nodes,
        edges=schematic_edges,
        labels=labels,
        symbols=symbols,
        work_zones=work_zones,
        included_codes=subgraph.included_codes,
        excluded_codes=subgraph.excluded_codes,
        warnings=warnings,
    )


def _assign_coordinates(
    nodes: dict[str, ElectricalGraphNode],
    adjacency: dict[str, set[str]],
    trunk: list[str],
    focus_id: str | None,
) -> dict[str, tuple[float, float]]:
    coordinates: dict[str, tuple[float, float]] = {}
    if not trunk:
        trunk = list(nodes)
    n = len(trunk)
    if n == 1:
        coordinates[trunk[0]] = (500.0, 210.0)
    else:
        start_x, end_x = 130.0, 870.0
        spacing = (end_x - start_x) / max(n - 1, 1)
        for idx, node_id in enumerate(trunk):
            coordinates[node_id] = (start_x + idx * spacing, 210.0)

    branch_slots: dict[str, int] = {}
    queue = deque(trunk)
    while queue:
        parent = queue.popleft()
        for child in sorted(adjacency.get(parent, set())):
            if child in coordinates or child not in nodes:
                continue
            slot = branch_slots.get(parent, 0)
            direction = -1 if slot % 2 == 0 else 1
            depth = slot // 2 + 1
            px, py = coordinates[parent]
            is_equipment = nodes[child].type not in {"POSTE", "EQUIPAMENTO_REFERENCIA"}
            dx = 0.0 if is_equipment else 105.0
            dy = direction * (42.0 if is_equipment else min(135.0, 82.0 * depth))
            coordinates[child] = (min(max(px + dx, 80.0), 920.0), min(max(py + dy, 72.0), 348.0))
            branch_slots[parent] = slot + 1
            queue.append(child)

    for idx, node_id in enumerate(node_id for node_id in nodes if node_id not in coordinates):
        row = idx // 5
        col = idx % 5
        coordinates[node_id] = (180.0 + col * 150.0, 92.0 + row * 82.0)

    if focus_id and focus_id in coordinates:
        _recentre_focus(coordinates, focus_id)
    return coordinates


def _recentre_focus(coordinates: dict[str, tuple[float, float]], focus_id: str) -> None:
    fx, fy = coordinates[focus_id]
    dx, dy = 500.0 - fx, 210.0 - fy
    for node_id, (x, y) in list(coordinates.items()):
        coordinates[node_id] = (
            min(max(x + dx, 70.0), 930.0),
            min(max(y + dy, 64.0), 356.0),
        )


def _trunk_path(
    nodes: dict[str, ElectricalGraphNode],
    adjacency: dict[str, set[str]],
    focus_id: str | None,
) -> list[str]:
    if not adjacency:
        return [focus_id] if focus_id and focus_id in nodes else list(nodes)[:1]
    endpoints = [node_id for node_id in nodes if len(adjacency.get(node_id, set())) <= 1]
    candidates = endpoints or list(nodes)
    if focus_id and focus_id in nodes:
        ranked = sorted(candidates, key=lambda node_id: _distance_to_focus(nodes, node_id, focus_id), reverse=True)
        left = ranked[0] if ranked else focus_id
        right = ranked[1] if len(ranked) > 1 else focus_id
        path = _shortest_path(left, right, adjacency)
        if focus_id not in path:
            left_path = _shortest_path(left, focus_id, adjacency)
            right_path = _shortest_path(focus_id, right, adjacency)
            path = [*left_path, *right_path[1:]]
        return path or [focus_id]
    left = candidates[0]
    right = max(candidates, key=lambda node_id: _distance_to_focus(nodes, node_id, left))
    return _shortest_path(left, right, adjacency) or list(nodes)[: min(6, len(nodes))]


def _shortest_path(start: str, end: str, adjacency: dict[str, set[str]]) -> list[str]:
    if start == end:
        return [start]
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node_id, path = queue.popleft()
        for neighbor in sorted(adjacency.get(node_id, set())):
            if neighbor in seen:
                continue
            next_path = [*path, neighbor]
            if neighbor == end:
                return next_path
            seen.add(neighbor)
            queue.append((neighbor, next_path))
    return []


def _schematic_edge(edge: ElectricalGraphEdge, coordinates: dict[str, tuple[float, float]]) -> SchematicEdge:
    start = coordinates[edge.from_node]
    end = coordinates[edge.to_node]
    if abs(start[0] - end[0]) < 2 or abs(start[1] - end[1]) < 2:
        points = [start, end]
    else:
        elbow = (end[0], start[1])
        points = [start, elbow, end]
    return SchematicEdge(
        id=edge.id,
        from_node=edge.from_node,
        to_node=edge.to_node,
        type=edge.type,
        points=[(round(x, 2), round(y, 2)) for x, y in points],
    )


def _labels(nodes: list[SchematicNode]) -> list[SchematicLabel]:
    labels = []
    for node in nodes:
        text = node.code or node.id
        if not text:
            continue
        offset_y = -22.0 if node.type in {"POSTE", "EQUIPAMENTO_REFERENCIA"} else 34.0
        labels.append(
            SchematicLabel(
                text=text,
                x=node.x + 10.0,
                y=node.y + offset_y,
                target_id=node.id,
                role="focus_label" if node.is_focus else "label",
                min_font_size=14.0 if node.is_focus else 13.0,
            )
        )
    return labels


def _symbols(nodes: list[SchematicNode]) -> list[SchematicSymbol]:
    symbols = []
    for node in nodes:
        if node.type in {"POSTE", "EQUIPAMENTO_REFERENCIA"}:
            kind = "POSTE"
        else:
            kind = node.type
        symbols.append(
            SchematicSymbol(
                kind=kind,
                code=node.code,
                node_id=node.id,
                x=node.x,
                y=node.y,
                label=node.code or node.id,
            )
        )
    return symbols


def _work_zones(
    nodes: list[SchematicNode],
    selected_code: str | None,
    focus_id: str | None,
) -> list[SchematicWorkZone]:
    focus = next((node for node in nodes if node.code == selected_code), None)
    if focus is None and focus_id:
        focus = next((node for node in nodes if node.id == focus_id), None)
    if focus is None:
        return []
    return [SchematicWorkZone(x=focus.x + 22.0, y=focus.y - 8.0, width=118.0, height=64.0)]


def _adjacency(edges: list[ElectricalGraphEdge]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for edge in edges:
        out.setdefault(edge.from_node, set()).add(edge.to_node)
        out.setdefault(edge.to_node, set()).add(edge.from_node)
    return out


def _focus_node_id(nodes: list[ElectricalGraphNode], selected_code: str | None) -> str | None:
    if selected_code:
        for node in nodes:
            if node.code == selected_code:
                return node.id
    return nodes[0].id if nodes else None


def _distance_to_focus(nodes: dict[str, ElectricalGraphNode], node_id: str, focus_id: str) -> float:
    return _distance(nodes.get(node_id), nodes.get(focus_id))


def _distance(left: ElectricalGraphNode | None, right: ElectricalGraphNode | None) -> float:
    if left is None or right is None or left.position_original is None or right.position_original is None:
        return 0.0 if left and right and left.id == right.id else 1.0
    return ((left.position_original[0] - right.position_original[0]) ** 2 + (left.position_original[1] - right.position_original[1]) ** 2) ** 0.5
