from __future__ import annotations

import math

from sistema.parsing.entities import Position, ProjectExtraction, StructureType


_EPSILON = 1e-7


def _intersection(first, second) -> tuple[float, float, float, float] | None:
    """Return (x, y, t, u) for a proper finite-segment intersection."""

    ax, ay = first.x1, first.y1
    bx, by = second.x1, second.y1
    rx, ry = first.x2 - ax, first.y2 - ay
    sx, sy = second.x2 - bx, second.y2 - by
    cross = rx * sy - ry * sx
    if abs(cross) <= 1e-9:
        return None
    qx, qy = bx - ax, by - ay
    t = (qx * sy - qy * sx) / cross
    u = (qx * ry - qy * rx) / cross
    if not (-_EPSILON <= t <= 1.0 + _EPSILON and -_EPSILON <= u <= 1.0 + _EPSILON):
        return None
    t = max(0.0, min(1.0, t))
    u = max(0.0, min(1.0, u))
    return ax + rx * t, ay + ry * t, t, u


def _interior(parameter: float) -> bool:
    return 1e-5 < parameter < 1.0 - 1e-5


def _has_structure(extraction: ProjectExtraction, page: int, x: float, y: float, code: str, tolerance: float) -> bool:
    page_height = extraction.page_sizes[page][1]
    return any(
        structure.codigo == code
        and structure.position.page == page
        and math.hypot(
            structure.position.x - x,
            structure.position.y_pdf(page_height) - y,
        ) <= tolerance
        for structure in extraction.structure_types
    )


def _has_pole(extraction: ProjectExtraction, page: int, x: float, y: float, tolerance: float) -> bool:
    page_height = extraction.page_sizes[page][1]
    return any(
        pole.position.page == page
        and math.hypot(
            pole.position.x - x,
            pole.position.y_pdf(page_height) - y,
        ) <= tolerance
        for pole in extraction.poles
    )


def mark_unverified_crossings_as_non_connections(extraction: ProjectExtraction) -> int:
    """Protect BT/MT topology from false junctions at visual line crossings.

    The PDF contains conductor vectors, but an interior/interior crossing alone is
    not proof of an electrical junction. A crossing is allowed to become a graph
    connection only when there is a pole or an explicit CRUZAMENTO_COM_CONEXAO
    marker at that point. Otherwise we add the official
    CRUZAMENTO_SEM_CONEXAO topology marker consumed by build_network_graph().

    Endpoint contacts are intentionally left untouched because they represent a
    deliberate vector termination against another conductor.
    """

    added = 0
    pages = sorted(extraction.page_sizes)
    for page in pages:
        width, height = extraction.page_sizes[page]
        scale = min(width, height)
        snap_tolerance = max(1.0, scale * 0.003)
        pole_tolerance = max(8.0, scale * 0.0178)
        indexes = [
            index
            for index, segment in enumerate(extraction.conductors)
            if segment.page == page
        ]
        for offset, first_index in enumerate(indexes):
            first = extraction.conductors[first_index]
            for second_index in indexes[:offset]:
                second = extraction.conductors[second_index]
                if first.tensao != second.tensao:
                    continue
                hit = _intersection(first, second)
                if hit is None:
                    continue
                x, y, first_t, second_t = hit
                if not (_interior(first_t) and _interior(second_t)):
                    continue
                if _has_structure(extraction, page, x, y, "CRUZAMENTO_SEM_CONEXAO", snap_tolerance * 1.5):
                    continue
                if _has_structure(extraction, page, x, y, "CRUZAMENTO_COM_CONEXAO", snap_tolerance * 1.5):
                    continue
                if _has_pole(extraction, page, x, y, pole_tolerance):
                    continue
                extraction.structure_types.append(
                    StructureType(
                        codigo="CRUZAMENTO_SEM_CONEXAO",
                        position=Position.from_pdf(page, x, y, height),
                        project_kind="AUTO_CROSSING_GUARD",
                        tension=first.tensao,
                        evidence="btmit_geometry_guard",
                        confidence=1.0,
                    )
                )
                added += 1
    return added
