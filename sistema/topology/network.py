from __future__ import annotations

import heapq
import math
import re
from dataclasses import asdict, dataclass, field

from sistema.extractors._pdf_geometry import point_segment_distance
from sistema.parsing.entities import ConductorSegment, Position, ProjectExtraction


@dataclass(frozen=True)
class GraphNode:
    id: int
    x: float
    y: float
    kind: str
    tension: str = ""
    pole_index: int | None = None


@dataclass(frozen=True)
class GraphEdge:
    id: int
    start: int
    end: int
    length: float
    kind: str
    segment_index: int | None = None
    t0: float = 0.0
    t1: float = 1.0


@dataclass
class NetworkGraph:
    page: int
    snap_tolerance: float
    pole_tolerance: float
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    adjacency: dict[int, list[tuple[int, int, float]]] = field(default_factory=dict)
    pole_nodes: dict[int, int] = field(default_factory=dict)
    component_by_node: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "snap_tolerance": round(self.snap_tolerance, 4),
            "pole_tolerance": round(self.pole_tolerance, 4),
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "pole_nodes": {str(key): value for key, value in self.pole_nodes.items()},
            "component_by_node": {
                str(key): value for key, value in self.component_by_node.items()
            },
        }


@dataclass
class NetworkSelection:
    page: int
    segment_ranges: dict[int, list[tuple[float, float]]]
    pole_indexes: set[int]
    anchor_codes: list[str]
    primary_code: str
    component: int | None
    graph: NetworkGraph
    warnings: list[str] = field(default_factory=list)

    @property
    def segment_indexes(self) -> set[int]:
        return set(self.segment_ranges)

    def to_dict(self, extraction: ProjectExtraction) -> dict:
        poles = []
        for index in sorted(self.pole_indexes):
            pole = extraction.poles[index]
            height = extraction.page_sizes[pole.position.page][1]
            poles.append(
                {
                    "index": index,
                    "code": pole.codigo,
                    "x": round(pole.position.x, 4),
                    "y": round(pole.position.y_pdf(height), 4),
                }
            )
        ranges = []
        voltage_counts: dict[str, int] = {}
        for segment_index in sorted(self.segment_ranges):
            segment = extraction.conductors[segment_index]
            voltage_counts[segment.tensao] = voltage_counts.get(segment.tensao, 0) + 1
            for t0, t1 in self.segment_ranges[segment_index]:
                ranges.append(
                    {
                        "segment_index": segment_index,
                        "tension": segment.tensao,
                        "t0": round(t0, 6),
                        "t1": round(t1, 6),
                    }
                )
        return {
            "status": "needs_review" if self.warnings else "selected",
            "warnings": self.warnings,
            "page": self.page,
            "primary_code": self.primary_code,
            "anchor_codes": self.anchor_codes,
            "component": self.component,
            "selected_poles": poles,
            "selected_ranges": ranges,
            "selected_pole_count": len(poles),
            "selected_segment_count": len(self.segment_indexes),
            "selected_voltage_segment_counts": voltage_counts,
            "graph": self.graph.to_dict(),
        }


def _numeric_code(value: str) -> str:
    match = re.search(r"\b(\d{6,7})\b", str(value))
    return match.group(1) if match else ""


def _projection_parameter(x: float, y: float, segment: ConductorSegment) -> float:
    dx = segment.x2 - segment.x1
    dy = segment.y2 - segment.y1
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return 0.0
    return max(0.0, min(1.0, ((x - segment.x1) * dx + (y - segment.y1) * dy) / denom))


def _point_at(segment: ConductorSegment, t: float) -> tuple[float, float]:
    return (
        segment.x1 + (segment.x2 - segment.x1) * t,
        segment.y1 + (segment.y2 - segment.y1) * t,
    )


def _intersection_parameters(
    first: ConductorSegment,
    second: ConductorSegment,
    tolerance: float,
) -> list[tuple[float, float]]:
    """Return real crossings and near endpoint contacts without changing geometry."""

    ax, ay = first.x1, first.y1
    bx, by = second.x1, second.y1
    rx, ry = first.x2 - ax, first.y2 - ay
    sx, sy = second.x2 - bx, second.y2 - by
    cross = rx * sy - ry * sx
    result: list[tuple[float, float]] = []
    if abs(cross) > 1e-9:
        qx, qy = bx - ax, by - ay
        t = (qx * sy - qy * sx) / cross
        u = (qx * ry - qy * rx) / cross
        if -1e-7 <= t <= 1.0000001 and -1e-7 <= u <= 1.0000001:
            result.append((max(0.0, min(1.0, t)), max(0.0, min(1.0, u))))

    endpoints = [
        (first.x1, first.y1, 0.0, second, False),
        (first.x2, first.y2, 1.0, second, False),
        (second.x1, second.y1, 0.0, first, True),
        (second.x2, second.y2, 1.0, first, True),
    ]
    for x, y, fixed_t, target, swapped in endpoints:
        if point_segment_distance(x, y, target) > tolerance:
            continue
        projected = _projection_parameter(x, y, target)
        pair = (projected, fixed_t) if swapped else (fixed_t, projected)
        if not any(abs(pair[0] - old[0]) < 1e-7 and abs(pair[1] - old[1]) < 1e-7 for old in result):
            result.append(pair)
    return result


def build_network_graph(
    extraction: ProjectExtraction,
    page: int,
    *,
    snap_tolerance: float | None = None,
    pole_tolerance: float | None = None,
) -> NetworkGraph:
    """Split conductor geometry at contacts, crossings and detected poles."""

    width, height = extraction.page_sizes[page]
    scale = min(width, height)
    snap_tolerance = snap_tolerance if snap_tolerance is not None else max(1.0, scale * 0.003)
    pole_tolerance = pole_tolerance if pole_tolerance is not None else max(8.0, scale * 0.0178)
    graph = NetworkGraph(page, snap_tolerance, pole_tolerance)

    segment_indexes = [
        index for index, segment in enumerate(extraction.conductors) if segment.page == page
    ]
    cuts: dict[int, set[float]] = {index: {0.0, 1.0} for index in segment_indexes}
    pole_cuts: dict[int, list[tuple[int, float]]] = {}

    for offset, first_index in enumerate(segment_indexes):
        first = extraction.conductors[first_index]
        for second_index in segment_indexes[:offset]:
            second = extraction.conductors[second_index]
            if first.tensao != second.tensao:
                continue
            for first_t, second_t in _intersection_parameters(first, second, snap_tolerance):
                cuts[first_index].add(first_t)
                cuts[second_index].add(second_t)

    for pole_index, pole in enumerate(extraction.poles):
        if pole.position.page != page:
            continue
        x = pole.position.x
        y = pole.position.y_pdf(height)
        for segment_index in segment_indexes:
            segment = extraction.conductors[segment_index]
            if point_segment_distance(x, y, segment) > pole_tolerance:
                continue
            t = _projection_parameter(x, y, segment)
            cuts[segment_index].add(t)
            pole_cuts.setdefault(pole_index, []).append((segment_index, t))

    namespaces: dict[str, list[int]] = {}

    def get_node(x: float, y: float, *, kind: str, tension: str = "", pole_index: int | None = None) -> int:
        namespace = f"{kind}:{tension}" if kind != "pole" else f"pole:{pole_index}"
        for node_id in namespaces.get(namespace, []):
            node = graph.nodes[node_id]
            if math.hypot(node.x - x, node.y - y) <= snap_tolerance:
                return node_id
        node_id = len(graph.nodes)
        graph.nodes.append(GraphNode(node_id, x, y, kind, tension, pole_index))
        graph.adjacency[node_id] = []
        namespaces.setdefault(namespace, []).append(node_id)
        return node_id

    def add_edge(
        start: int,
        end: int,
        length: float,
        kind: str,
        segment_index: int | None = None,
        t0: float = 0.0,
        t1: float = 1.0,
    ) -> int:
        if start == end:
            return -1
        edge_id = len(graph.edges)
        edge = GraphEdge(edge_id, start, end, max(length, 1e-6), kind, segment_index, t0, t1)
        graph.edges.append(edge)
        graph.adjacency[start].append((end, edge_id, edge.length))
        graph.adjacency[end].append((start, edge_id, edge.length))
        return edge_id

    cut_nodes: dict[tuple[int, float], int] = {}
    for segment_index in segment_indexes:
        segment = extraction.conductors[segment_index]
        ordered = sorted(cuts[segment_index])
        for t in ordered:
            x, y = _point_at(segment, t)
            cut_nodes[(segment_index, t)] = get_node(
                x, y, kind="conductor", tension=segment.tensao
            )
        for t0, t1 in zip(ordered, ordered[1:]):
            if t1 - t0 <= 1e-8:
                continue
            start = cut_nodes[(segment_index, t0)]
            end = cut_nodes[(segment_index, t1)]
            add_edge(
                start,
                end,
                segment.length * (t1 - t0),
                "conductor",
                segment_index,
                t0,
                t1,
            )

    for pole_index, attachments in pole_cuts.items():
        pole = extraction.poles[pole_index]
        x = pole.position.x
        y = pole.position.y_pdf(height)
        pole_node = get_node(x, y, kind="pole", pole_index=pole_index)
        graph.pole_nodes[pole_index] = pole_node
        for segment_index, t in attachments:
            conductor_node = cut_nodes[(segment_index, t)]
            node = graph.nodes[conductor_node]
            add_edge(pole_node, conductor_node, math.hypot(node.x - x, node.y - y), "attachment")

    component = 0
    for start in range(len(graph.nodes)):
        if start in graph.component_by_node:
            continue
        stack = [start]
        graph.component_by_node[start] = component
        while stack:
            node = stack.pop()
            for neighbor, _, _ in graph.adjacency[node]:
                if neighbor in graph.component_by_node:
                    continue
                graph.component_by_node[neighbor] = component
                stack.append(neighbor)
        component += 1
    return graph


def _shortest_path(
    graph: NetworkGraph,
    start: int,
    targets: set[int] | None = None,
) -> tuple[dict[int, float], dict[int, tuple[int, int]]]:
    distances = {start: 0.0}
    previous: dict[int, tuple[int, int]] = {}
    queue = [(0.0, start)]
    remaining = set(targets or [])
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        remaining.discard(node)
        if targets is not None and not remaining:
            break
        for neighbor, edge_id, weight in graph.adjacency[node]:
            candidate = distance + weight
            if candidate + 1e-9 >= distances.get(neighbor, math.inf):
                continue
            distances[neighbor] = candidate
            previous[neighbor] = (node, edge_id)
            heapq.heappush(queue, (candidate, neighbor))
    return distances, previous


def _restore_path(
    start: int,
    end: int,
    previous: dict[int, tuple[int, int]],
) -> tuple[set[int], set[int]]:
    nodes = {end}
    edges: set[int] = set()
    current = end
    while current != start and current in previous:
        parent, edge_id = previous[current]
        nodes.add(parent)
        edges.add(edge_id)
        current = parent
    return nodes, edges


def _equipment_positions(extraction: ProjectExtraction) -> dict[str, Position]:
    result: dict[str, Position] = {}
    for item in [*extraction.transformers, *extraction.existing_equipment]:
        if item.numero:
            result.setdefault(item.numero, item.position)
    return result


def _semantic_codes(projeto: dict) -> list[str]:
    result: list[str] = []
    meta = projeto.get("meta", {}) if isinstance(projeto, dict) else {}
    rows = projeto.get("equipamentos", []) if isinstance(projeto, dict) else []
    for raw in [meta.get("equipamento", ""), *[row.get("codigo", "") for row in rows if isinstance(row, dict)]]:
        code = _numeric_code(raw)
        if code and code not in result:
            result.append(code)
    return result


def _nearest_pole_index(
    extraction: ProjectExtraction,
    position: Position,
    page: int,
) -> int | None:
    height = extraction.page_sizes[page][1]
    candidates = []
    for index, pole in enumerate(extraction.poles):
        if pole.position.page != page:
            continue
        distance = math.hypot(
            pole.position.x - position.x,
            pole.position.y_pdf(height) - position.y_pdf(height),
        )
        candidates.append((distance, index))
    return min(candidates)[1] if candidates else None


def _anchor_nodes(
    extraction: ProjectExtraction,
    projeto: dict,
    graph: NetworkGraph,
) -> tuple[str, list[tuple[str, int, int]]]:
    max_equipment_anchors = 8
    equipment = _equipment_positions(extraction)
    semantic_codes = _semantic_codes(projeto)
    primary_code = next(
        (
            code
            for code in [
                *semantic_codes,
                _numeric_code(extraction.metadata.get("equipamento", "")),
            ]
            if code
        ),
        "",
    )
    ordered_codes = list(semantic_codes)
    if primary_code and primary_code not in ordered_codes:
        ordered_codes.insert(0, primary_code)

    pole_by_code = {
        pole.codigo.upper(): index for index, pole in enumerate(extraction.poles)
    }
    explicit_poles: dict[str, int] = {}
    for row in projeto.get("equipamentos", []) if isinstance(projeto, dict) else []:
        if not isinstance(row, dict):
            continue
        code = _numeric_code(row.get("codigo", ""))
        node_id = str(row.get("no_id", "")).strip().upper()
        if code and node_id in pole_by_code:
            explicit_poles[code] = pole_by_code[node_id]

    anchors = []
    for code in ordered_codes:
        pole_index = None
        position = equipment.get(code)
        if position is not None and position.page == graph.page:
            pole_index = _nearest_pole_index(extraction, position, graph.page)
        if pole_index is None:
            pole_index = explicit_poles.get(code)
        if pole_index is None or pole_index not in graph.pole_nodes:
            continue
        anchors.append((code, pole_index, graph.pole_nodes[pole_index]))

    # Semantic extraction can miss secondary labels even when their positions
    # and codes are verified in the CAD PDF. Complete the anchor set with a
    # bounded number of source assets nearest to the service. This preserves
    # required transformer and switch context without selecting the whole map.
    if len(anchors) < max_equipment_anchors and equipment:
        origin_position = equipment.get(primary_code)
        if origin_position is None and anchors:
            origin_pole = extraction.poles[anchors[0][1]]
            origin_position = origin_pole.position
        if origin_position is None:
            origin_position = next(
                (position for position in equipment.values() if position.page == graph.page),
                None,
            )
        candidates = []
        if origin_position is not None:
            height = extraction.page_sizes[graph.page][1]
            ox = origin_position.x
            oy = origin_position.y_pdf(height)
            existing_codes = {code for code, _, _ in anchors}
            for code, position in equipment.items():
                if code in existing_codes or position.page != graph.page:
                    continue
                distance = math.hypot(position.x - ox, position.y_pdf(height) - oy)
                candidates.append((distance, code, position))
        for _, code, position in sorted(candidates, key=lambda row: (row[0], row[1])):
            if len(anchors) >= max_equipment_anchors:
                break
            pole_index = _nearest_pole_index(extraction, position, graph.page)
            if pole_index is None or pole_index not in graph.pole_nodes:
                continue
            if any(existing[1] == pole_index for existing in anchors):
                continue
            anchors.append((code, pole_index, graph.pole_nodes[pole_index]))
    if not anchors and graph.pole_nodes:
        pole_index = min(graph.pole_nodes)
        anchors.append(("", pole_index, graph.pole_nodes[pole_index]))
    return primary_code, anchors


def _minimum_anchor_paths(
    graph: NetworkGraph,
    anchor_nodes: list[int],
) -> tuple[set[int], set[int]]:
    if not anchor_nodes:
        return set(), set()
    unique = list(dict.fromkeys(anchor_nodes))
    tree = {unique[0]}
    selected_nodes = {unique[0]}
    selected_edges: set[int] = set()
    while len(tree) < len(unique):
        best = None
        for start in tree:
            targets = set(unique) - tree
            distances, previous = _shortest_path(graph, start, targets)
            for target in targets:
                distance = distances.get(target)
                if distance is None:
                    continue
                candidate = (distance, start, target, previous)
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        if best is None:
            break
        _, start, target, previous = best
        nodes, edges = _restore_path(start, target, previous)
        selected_nodes.update(nodes)
        selected_edges.update(edges)
        tree.add(target)
    return selected_nodes, selected_edges


def _pole_neighbors(graph: NetworkGraph) -> dict[int, list[tuple[int, set[int], set[int], float]]]:
    """Collapse geometry nodes into direct pole-to-pole spans."""

    pole_node_to_index = {node: index for index, node in graph.pole_nodes.items()}
    conductor_to_poles: dict[int, list[tuple[int, int, float]]] = {}
    for edge in graph.edges:
        if edge.kind != "attachment":
            continue
        start = graph.nodes[edge.start]
        end = graph.nodes[edge.end]
        if start.kind == "pole":
            pole_node, conductor_node = start, end
        elif end.kind == "pole":
            pole_node, conductor_node = end, start
        else:
            continue
        if pole_node.pole_index is not None:
            conductor_to_poles.setdefault(conductor_node.id, []).append(
                (pole_node.pole_index, edge.id, edge.length)
            )
    result: dict[int, list[tuple[int, set[int], set[int], float]]] = {
        index: [] for index in graph.pole_nodes
    }
    for pole_index, start in graph.pole_nodes.items():
        distances = {start: 0.0}
        previous: dict[int, tuple[int, int]] = {}
        queue = [(0.0, start)]
        reached: set[int] = set()
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances.get(node):
                continue
            attached = [item for item in conductor_to_poles.get(node, []) if item[0] != pole_index]
            if attached:
                for other_index, edge_id, weight in attached:
                    pole_node = graph.pole_nodes[other_index]
                    candidate = distance + weight
                    if candidate < distances.get(pole_node, math.inf):
                        distances[pole_node] = candidate
                        previous[pole_node] = (node, edge_id)
                    reached.add(pole_node)
                continue
            for neighbor, edge_id, weight in graph.adjacency[node]:
                candidate = distance + weight
                if candidate + 1e-9 >= distances.get(neighbor, math.inf):
                    continue
                distances[neighbor] = candidate
                previous[neighbor] = (node, edge_id)
                heapq.heappush(queue, (candidate, neighbor))
        for node in reached:
            other_index = pole_node_to_index[node]
            nodes, edges = _restore_path(start, node, previous)
            result[pole_index].append((other_index, nodes, edges, distances[node]))
    return result


def _pole_neighbors_by_tension(
    graph: NetworkGraph,
) -> dict[int, list[tuple[int, set[int], set[int], float]]]:
    """Return direct pole spans without allowing a path to change voltage.

    A pole can support both MT and BT. The general graph intentionally joins
    those layers at the pole so the service component can be selected as one
    network. For rendering, however, choosing only the shortest pole-to-pole
    path drops the parallel layer. This traversal runs once per voltage and
    stops at the next pole, preserving every CAD conductor that shares the
    selected pole corridor.
    """

    tensions = sorted(
        {
            node.tension
            for node in graph.nodes
            if node.kind == "conductor" and node.tension
        }
    )
    pole_node_to_index = {node: index for index, node in graph.pole_nodes.items()}
    result: dict[int, list[tuple[int, set[int], set[int], float]]] = {
        index: [] for index in graph.pole_nodes
    }

    for pole_index, start in graph.pole_nodes.items():
        for tension in tensions:
            distances = {start: 0.0}
            previous: dict[int, tuple[int, int]] = {}
            queue = [(0.0, start)]
            reached: set[int] = set()
            while queue:
                distance, node = heapq.heappop(queue)
                if distance != distances.get(node):
                    continue
                current = graph.nodes[node]
                if node != start and current.kind == "pole":
                    reached.add(node)
                    continue

                for neighbor, edge_id, weight in graph.adjacency[node]:
                    edge = graph.edges[edge_id]
                    target = graph.nodes[neighbor]
                    if edge.kind == "conductor":
                        if current.tension != tension or target.tension != tension:
                            continue
                    elif edge.kind == "attachment":
                        conductor = target if target.kind == "conductor" else current
                        if conductor.kind != "conductor" or conductor.tension != tension:
                            continue
                        if current.kind == "pole" and node != start:
                            continue
                    else:
                        continue

                    candidate = distance + weight
                    if candidate + 1e-9 >= distances.get(neighbor, math.inf):
                        continue
                    distances[neighbor] = candidate
                    previous[neighbor] = (node, edge_id)
                    heapq.heappush(queue, (candidate, neighbor))

            for pole_node in reached:
                other_index = pole_node_to_index[pole_node]
                nodes, edges = _restore_path(start, pole_node, previous)
                result[pole_index].append(
                    (other_index, nodes, edges, distances[pole_node])
                )
    return result


def _include_parallel_networks(
    graph: NetworkGraph,
    selected_poles: set[int],
    selected_nodes: set[int],
    selected_edges: set[int],
) -> None:
    """Complete the selected corridor with every MT/BT span evidenced by CAD."""

    spans = _pole_neighbors_by_tension(graph)
    for pole_index in selected_poles:
        for other, nodes, edges, _ in spans.get(pole_index, []):
            if other not in selected_poles:
                continue
            selected_nodes.update(nodes)
            selected_edges.update(edges)


def _expand_context(
    graph: NetworkGraph,
    neighbors: dict[int, list[tuple[int, set[int], set[int], float]]],
    seed_poles: set[int],
    *,
    hops: int,
    max_poles: int,
) -> tuple[set[int], set[int], set[int]]:
    selected_poles = set(seed_poles)
    selected_nodes = {graph.pole_nodes[index] for index in seed_poles}
    selected_edges: set[int] = set()
    frontier = set(seed_poles)
    for _ in range(hops):
        candidates = []
        for pole_index in frontier:
            for other, nodes, edges, distance in neighbors.get(pole_index, []):
                if other in selected_poles:
                    continue
                candidates.append((distance, pole_index, other, nodes, edges))
        next_frontier: set[int] = set()
        for _, _, other, nodes, edges in sorted(candidates, key=lambda row: row[:3]):
            if len(selected_poles) >= max_poles:
                break
            if other in selected_poles:
                continue
            selected_poles.add(other)
            selected_nodes.update(nodes)
            selected_edges.update(edges)
            next_frontier.add(other)
        frontier = next_frontier
        if not frontier:
            break
    return selected_poles, selected_nodes, selected_edges


def _ranges_from_edges(graph: NetworkGraph, edge_ids: set[int]) -> dict[int, list[tuple[float, float]]]:
    raw: dict[int, list[tuple[float, float]]] = {}
    for edge_id in edge_ids:
        edge = graph.edges[edge_id]
        if edge.kind != "conductor" or edge.segment_index is None:
            continue
        raw.setdefault(edge.segment_index, []).append((min(edge.t0, edge.t1), max(edge.t0, edge.t1)))
    result: dict[int, list[tuple[float, float]]] = {}
    for segment_index, ranges in raw.items():
        merged: list[list[float]] = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1][1] + 1e-7:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        result[segment_index] = [(start, end) for start, end in merged]
    return result


def _poles_touching_nodes(
    graph: NetworkGraph,
    nodes: set[int],
    component: int | None,
) -> set[int]:
    result = set()
    for index, pole_node in graph.pole_nodes.items():
        if component is not None and graph.component_by_node.get(pole_node) != component:
            continue
        attached_nodes = {
            neighbor
            for neighbor, edge_id, _ in graph.adjacency[pole_node]
            if graph.edges[edge_id].kind == "attachment"
        }
        if pole_node in nodes or attached_nodes.intersection(nodes):
            result.add(index)
    return result


def select_service_network(
    extraction: ProjectExtraction,
    projeto: dict,
    page: int,
    *,
    context_hops: int = 2,
    max_context_poles: int | None = None,
) -> NetworkSelection:
    """Select the connected conductor subgraph that supports the service."""

    graph = build_network_graph(extraction, page)
    primary_code, anchors = _anchor_nodes(extraction, projeto, graph)
    page_segment_count = sum(
        segment.page == page for segment in extraction.conductors
    )
    page_pole_count = sum(pole.position.page == page for pole in extraction.poles)
    source_warnings = []
    if page_segment_count < 5 and page_pole_count < 3:
        source_warnings.extend(["LOW_CONDUCTOR_COVERAGE", "LOW_POLE_COVERAGE"])
    if not anchors:
        page_segments = {
            index: [(0.0, 1.0)]
            for index, segment in enumerate(extraction.conductors)
            if segment.page == page
        }
        page_poles = {
            index
            for index, pole in enumerate(extraction.poles)
            if pole.position.page == page
        }
        return NetworkSelection(
            page,
            page_segments,
            page_poles,
            [],
            primary_code,
            None,
            graph,
            [*source_warnings, "NO_SERVICE_ANCHOR"],
        )

    primary = next((item for item in anchors if item[0] == primary_code), anchors[0])
    component = graph.component_by_node.get(primary[2])
    anchors = [item for item in anchors if graph.component_by_node.get(item[2]) == component]
    warnings = list(source_warnings)
    if not any(code for code, _, _ in anchors):
        warnings.append("NO_SERVICE_ANCHOR")
    if primary_code and primary_code not in {code for code, _, _ in anchors}:
        warnings.append("PRIMARY_EQUIPMENT_NOT_POSITIONED")
    anchor_nodes = [item[2] for item in anchors]
    selected_nodes, selected_edges = _minimum_anchor_paths(graph, anchor_nodes)

    core_poles = _poles_touching_nodes(graph, selected_nodes, component)
    if not core_poles:
        core_poles = {primary[1]}
    if max_context_poles is None:
        context_budget = max(4, min(12, round(len(core_poles) * 0.32)))
        max_context_poles = len(core_poles) + context_budget
    neighbors = _pole_neighbors(graph)
    context_poles, context_nodes, context_edges = _expand_context(
        graph,
        neighbors,
        core_poles,
        hops=context_hops if len(anchors) > 1 else max(2, context_hops),
        max_poles=max_context_poles,
    )
    selected_nodes.update(context_nodes)
    selected_edges.update(context_edges)

    # Preserve every pole lying on the chosen geometry, including unlabelled
    # intermediate supports that were not explicit equipment anchors.
    selected_poles = _poles_touching_nodes(graph, selected_nodes, component)
    selected_poles.update(context_poles)
    _include_parallel_networks(
        graph,
        selected_poles,
        selected_nodes,
        selected_edges,
    )
    return NetworkSelection(
        page=page,
        segment_ranges=_ranges_from_edges(graph, selected_edges),
        pole_indexes=selected_poles,
        anchor_codes=[code for code, _, _ in anchors if code],
        primary_code=primary_code,
        component=component,
        graph=graph,
        warnings=warnings,
    )
