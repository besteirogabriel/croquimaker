from __future__ import annotations

from collections import defaultdict, deque

from croqui_engine.core.models import Equipment, Node, Span, TechnicalPayload
from croqui_engine.parser.spatial import find_nearest_node


def build_graph(
    nodes: list[Node],
    spans: list[Span],
    equipment: list[Equipment],
    payload: TechnicalPayload | None = None,
) -> TechnicalPayload:
    payload = payload or TechnicalPayload()

    node_map: dict[str, Node] = {node.id: node for node in nodes}
    for span in spans:
        for node_id in (span.from_node, span.to_node):
            node_map.setdefault(node_id, Node(id=node_id, confidence=0.68, raw_text=f"Auto via {span.id}"))

    if not spans and equipment:
        _add_fallback_reference_layout(node_map, spans, equipment)

    ordered_nodes = sorted(
        node_map.values(),
        key=lambda n: int(n.id[1:]) if n.id.startswith("P") and n.id[1:].isdigit() else 99999,
    )

    _assign_missing_positions(ordered_nodes, spans)
    _associate_equipment(equipment, ordered_nodes)

    payload.nodes = ordered_nodes
    payload.spans = spans
    payload.equipment = equipment
    return payload


def _add_fallback_reference_layout(
    node_map: dict[str, Node], spans: list[Span], equipment: list[Equipment]
) -> None:
    """Create a visibly marked reference layout when topology was not extracted."""
    if node_map:
        for node in node_map.values():
            node.confidence = min(node.confidence, 0.55)
        return

    unique_equipment: list[Equipment] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in equipment:
        key = (item.code, item.type, item.status)
        if key in seen or item.deleted:
            continue
        seen.add(key)
        unique_equipment.append(item)

    for idx, item in enumerate(unique_equipment, start=1):
        node_id = f"EQ{idx}"
        node_map[node_id] = Node(
            id=node_id,
            type="EQUIPAMENTO_REFERENCIA",
            x=(idx - 1) * 120.0,
            y=0.0,
            confidence=0.42,
            raw_text=f"Referencia gerada para {item.type} {item.code}",
        )
        item.node_id = node_id
        item.confidence = max(item.confidence, 0.55)

    fallback_nodes = list(node_map)
    for idx in range(len(fallback_nodes) - 1):
        spans.append(
            Span(
                id=f"REF{idx + 1}-{idx + 2}",
                from_node=fallback_nodes[idx],
                to_node=fallback_nodes[idx + 1],
                network_type="REFERENCIA_REVISAO",
                status="referencia",
                confidence=0.25,
                raw_text="Ligacao referencial gerada para revisao humana; nao representa vao confirmado.",
            )
        )


def _associate_equipment(equipment: list[Equipment], nodes: list[Node]) -> None:
    if not nodes:
        return
    for item in equipment:
        if item.node_id:
            continue
        if item.bbox is not None:
            nearest = find_nearest_node(item.bbox, nodes, radius=180)
            if nearest:
                item.node_id = nearest.id
                item.confidence = max(item.confidence, 0.78)
                continue
        if len(nodes) == 1 and item.confidence < 0.8:
            item.node_id = nodes[0].id
            item.confidence = max(item.confidence, 0.55)


def _assign_missing_positions(nodes: list[Node], spans: list[Span]) -> None:
    if not nodes:
        return
    positioned = [node for node in nodes if node.x is not None and node.y is not None]
    if len(positioned) >= max(2, len(nodes) // 2):
        return

    adj: dict[str, set[str]] = defaultdict(set)
    for span in spans:
        adj[span.from_node].add(span.to_node)
        adj[span.to_node].add(span.from_node)

    node_map = {node.id: node for node in nodes}
    visited: set[str] = set()
    x_offset = 0.0
    spacing_x = 120.0
    spacing_y = 90.0

    for start in sorted(node_map, key=_node_sort_key):
        if start in visited:
            continue
        queue = deque([(start, x_offset, 0.0)])
        local_max_x = x_offset
        branch_count: dict[str, int] = defaultdict(int)

        while queue:
            node_id, x, y = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_map[node_id]
            if node.x is None or node.y is None:
                node.x = x
                node.y = y
            local_max_x = max(local_max_x, x)

            neighbors = [n for n in sorted(adj[node_id], key=_node_sort_key) if n not in visited]
            for idx, neighbor in enumerate(neighbors):
                if idx == 0:
                    queue.append((neighbor, x + spacing_x, y))
                else:
                    branch_count[node_id] += 1
                    direction = 1 if branch_count[node_id] % 2 else -1
                    queue.append((neighbor, x, y + direction * spacing_y * branch_count[node_id]))

        x_offset = local_max_x + spacing_x * 2


def _node_sort_key(value: str) -> int:
    if value.startswith("P") and value[1:].isdigit():
        return int(value[1:])
    return 999999
