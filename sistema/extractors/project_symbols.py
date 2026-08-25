from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

import fitz

from sistema.extractors._pdf_geometry import (
    classify_conductor_color,
    normalize_rgb,
    point_segment_distance,
)
from sistema.parsing.entities import (
    ConductorSegment,
    Pole,
    Position,
    ProjectExtraction,
    StructureType,
)


MAPPING_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "symbols"
    / "project_to_croqui_map.json"
)

POLE_BROWN = (0.398, 0.066, 0.0)
RED = (1.0, 0.0, 0.0)


@lru_cache(maxsize=1)
def load_project_symbol_mapping() -> dict:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    if mapping.get("version") != 1 or not mapping.get("rules"):
        raise ValueError("Catálogo DE-PARA de símbolos do projeto é inválido")
    return mapping


def croqui_symbol_for_project_kind(project_kind: str) -> str | None:
    rule = load_project_symbol_mapping()["rules"].get(str(project_kind).upper())
    return str(rule["croqui_symbol"]) if rule else None


def _color_close(value, expected: tuple[float, float, float], tolerance: float) -> bool:
    color = normalize_rgb(value)
    return color is not None and math.dist(color, expected) <= tolerance


def _rect_distance(rect: fitz.Rect, x: float, y: float) -> float:
    dx = max(rect.x0 - x, 0.0, x - rect.x1)
    dy = max(rect.y0 - y, 0.0, y - rect.y1)
    return math.hypot(dx, dy)


def classify_circular_pole(
    drawings: list[dict],
    x: float,
    y: float,
) -> str:
    """Distinguish the reviewed concrete and wood CAD pole profiles.

    Concrete poles contain two concentric brown contours. The wood profile has
    one circular contour split into two half paths. Small green/blue network
    markers are deliberately ignored because they are not part of the pole.
    """

    components = []
    for drawing in drawings:
        if not _color_close(drawing.get("color"), POLE_BROWN, 0.06):
            continue
        rect = fitz.Rect(drawing["rect"])
        if _rect_distance(rect, x, y) > 1.2:
            continue
        if not (2.0 <= max(rect.width, rect.height) <= 10.5):
            continue
        components.append(rect)

    has_single_full_width_contour = any(
        max(rect.width, rect.height) >= 7.0
        and min(rect.width, rect.height) <= 5.0
        for rect in components
    )
    has_concentric_components = len(components) >= 4 or len(
        {
            round(max(rect.width, rect.height), 1)
            for rect in components
            if max(rect.width, rect.height) >= 3.0
        }
    ) >= 2
    if has_single_full_width_contour and not has_concentric_components:
        return "POSTE_CIRCULAR_MADEIRA"
    return "POSTE_CIRCULAR_CONCRETO"


def has_replacement_marker(
    drawings: list[dict],
    x: float,
    y: float,
    *,
    radius: float = 8.0,
) -> bool:
    diagonals: list[tuple[float, float]] = []
    for drawing in drawings:
        colors = (drawing.get("color"), drawing.get("fill"))
        if not any(_color_close(color, RED, 0.10) for color in colors):
            continue
        rect = fitz.Rect(drawing["rect"])
        if _rect_distance(rect, x, y) > radius:
            continue
        for item in drawing.get("items", []):
            if item[0] != "l":
                continue
            start, end = item[1], item[2]
            dx = float(end.x - start.x)
            dy = float(end.y - start.y)
            length = math.hypot(dx, dy)
            if length < 2.0 or abs(dx) < length * 0.25 or abs(dy) < length * 0.25:
                continue
            diagonals.append((dx / length, dy / length))
    return any(
        first[0] * second[0] < -0.12 and first[1] * second[1] > 0.12
        or first[0] * second[0] > 0.12 and first[1] * second[1] < -0.12
        for index, first in enumerate(diagonals)
        for second in diagonals[index + 1 :]
    )


def detect_double_t_poles(
    page: fitz.Page,
    segments: list[ConductorSegment],
    *,
    page_no: int,
) -> list[tuple[float, float]]:
    """Find the I-shaped double-T pole reviewed as ICON-008."""

    candidates: list[tuple[float, float]] = []
    for drawing in page.get_drawings():
        if not _color_close(drawing.get("color"), POLE_BROWN, 0.06):
            continue
        rect = fitz.Rect(drawing["rect"])
        item_count = len(drawing.get("items", []))
        if not (
            drawing.get("type") == "s"
            and 7.5 <= rect.width <= 10.5
            and 7.5 <= rect.height <= 10.5
            and 8 <= item_count <= 16
        ):
            continue
        x = (rect.x0 + rect.x1) / 2
        y = (rect.y0 + rect.y1) / 2
        page_segments = [segment for segment in segments if segment.page == page_no]
        if page_segments and min(
            point_segment_distance(x, y, segment) for segment in page_segments
        ) > 12.0:
            continue
        if any(math.hypot(x - old_x, y - old_y) <= 4.0 for old_x, old_y in candidates):
            continue
        candidates.append((x, y))
    return candidates


def enrich_pole_profiles(
    doc: fitz.Document,
    poles: list[Pole],
    segments: list[ConductorSegment],
) -> list[Pole]:
    enriched: list[Pole] = []
    for pole in poles:
        page = doc[pole.position.page]
        x = pole.position.x
        y = pole.position.y_pdf(page.rect.height)
        project_kind = classify_circular_pole(page.get_drawings(), x, y)
        replacement = has_replacement_marker(page.get_drawings(), x, y)
        enriched.append(
            Pole(
                codigo=pole.codigo,
                position=pole.position,
                novo=pole.novo or replacement,
                project_kind=project_kind,
                croqui_symbol=(
                    "POSTE_NOVO"
                    if replacement
                    else croqui_symbol_for_project_kind(project_kind)
                    or "POSTE_CONCRETO"
                ),
                evidence="project_vector",
            )
        )

    for page_no, page in enumerate(doc):
        for x, y in detect_double_t_poles(page, segments, page_no=page_no):
            if any(
                pole.position.page == page_no
                and math.hypot(
                    pole.position.x - x,
                    pole.position.y_pdf(page.rect.height) - y,
                )
                <= 4.0
                for pole in enriched
            ):
                continue
            enriched.append(
                Pole(
                    codigo="AUTO",
                    position=Position.from_pdf(page_no, x, y, page.rect.height),
                    project_kind="POSTE_DUPLO_T",
                    croqui_symbol="POSTE_DUPLO_T",
                    evidence="project_vector",
                )
            )

    enriched.sort(
        key=lambda pole: (
            pole.position.page,
            pole.position.y_pdf(doc[pole.position.page].rect.height),
            pole.position.x,
        )
    )
    existing_auto_indexes = [
        int(match.group(1))
        for pole in enriched
        for match in [
            re.fullmatch(r"AUTO(\d+)", pole.codigo)
        ]
        if match
    ]
    auto_index = max(existing_auto_indexes, default=0) + 1
    result: list[Pole] = []
    for pole in enriched:
        code = pole.codigo
        if code == "AUTO":
            code = f"AUTO{auto_index}"
            auto_index += 1
        result.append(
            Pole(
                codigo=code,
                position=pole.position,
                novo=pole.novo,
                project_kind=pole.project_kind,
                croqui_symbol=pole.croqui_symbol,
                evidence=pole.evidence,
            )
        )
    return result


def _projection_parameter(x: float, y: float, segment: ConductorSegment) -> float:
    dx = segment.x2 - segment.x1
    dy = segment.y2 - segment.y1
    denominator = dx * dx + dy * dy
    if denominator <= 1e-12:
        return 0.0
    return max(
        0.0,
        min(
            1.0,
            ((x - segment.x1) * dx + (y - segment.y1) * dy) / denominator,
        ),
    )


def _segment_intersection(
    first: ConductorSegment,
    second: ConductorSegment,
) -> tuple[float, float, float, float] | None:
    ax, ay = first.x1, first.y1
    bx, by = second.x1, second.y1
    rx, ry = first.x2 - ax, first.y2 - ay
    sx, sy = second.x2 - bx, second.y2 - by
    denominator = rx * sy - ry * sx
    if abs(denominator) <= 1e-9:
        return None
    qx, qy = bx - ax, by - ay
    first_t = (qx * sy - qy * sx) / denominator
    second_t = (qx * ry - qy * rx) / denominator
    if not (-1e-7 <= first_t <= 1.0000001 and -1e-7 <= second_t <= 1.0000001):
        return None
    return (
        ax + first_t * rx,
        ay + first_t * ry,
        max(0.0, min(1.0, first_t)),
        max(0.0, min(1.0, second_t)),
    )


def _has_connection_dot(
    page: fitz.Page,
    x: float,
    y: float,
    tensions: set[str],
) -> bool:
    for drawing in page.get_drawings():
        rect = fitz.Rect(drawing["rect"])
        if max(rect.width, rect.height) > 5.0 or _rect_distance(rect, x, y) > 2.2:
            continue
        colors = (drawing.get("fill"), drawing.get("color"))
        for color in colors:
            classified = classify_conductor_color(color)
            normalized = normalize_rgb(color)
            is_dark_node = (
                normalized is not None
                and max(normalized) <= 0.55
                and (normalized[1] >= normalized[0] or normalized[2] >= normalized[0])
            )
            if classified in tensions or is_dark_node:
                return True
    return False


def _near_pole(
    poles: list[Pole],
    page_no: int,
    x: float,
    y: float,
    page_height: float,
    radius: float = 7.0,
) -> bool:
    return any(
        pole.position.page == page_no
        and math.hypot(
            pole.position.x - x,
            pole.position.y_pdf(page_height) - y,
        )
        <= radius
        for pole in poles
    )


def _direction_for_segment(
    segment: ConductorSegment,
) -> tuple[float, float]:
    dx = segment.x2 - segment.x1
    dy = segment.y2 - segment.y1
    length = math.hypot(dx, dy)
    return (1.0, 0.0) if length <= 1e-9 else (dx / length, -dy / length)


def _same_conductor_color(
    first: ConductorSegment,
    second: ConductorSegment,
    *,
    tolerance: float = 0.025,
) -> bool:
    """Return whether two crossing strokes belong to the same CAD color.

    Voltage classification is intentionally insufficient here: a visual
    crossing symbol is only valid when the actual source strokes have the
    same color. Different colors represent independent overlaid networks.
    """

    first_color = normalize_rgb(first.color)
    second_color = normalize_rgb(second.color)
    return (
        first_color is not None
        and second_color is not None
        and math.dist(first_color, second_color) <= tolerance
    )


def _crossing_structures(
    doc: fitz.Document,
    extraction: ProjectExtraction,
) -> list[StructureType]:
    result: list[StructureType] = []
    for page_no, page in enumerate(doc):
        segments = [
            segment
            for segment in extraction.conductors
            if segment.page == page_no
        ]
        for index, first in enumerate(segments):
            for second in segments[:index]:
                # A blue/green (or otherwise differently coloured) overlap is
                # not a crossing symbol. The networks merely pass over one
                # another and must remain visually and topologically separate.
                if not _same_conductor_color(first, second):
                    continue
                intersection = _segment_intersection(first, second)
                if intersection is None:
                    continue
                x, y, first_t, second_t = intersection
                first_dx = first.x2 - first.x1
                first_dy = first.y2 - first.y1
                second_dx = second.x2 - second.x1
                second_dy = second.y2 - second.y1
                angle_factor = abs(first_dx * second_dy - first_dy * second_dx) / max(
                    first.length * second.length,
                    1e-9,
                )
                if angle_factor < 0.25:
                    continue
                if _near_pole(
                    extraction.poles,
                    page_no,
                    x,
                    y,
                    page.rect.height,
                ):
                    continue
                shared_endpoint = (
                    first_t <= 0.015 or first_t >= 0.985
                ) and (
                    second_t <= 0.015 or second_t >= 0.985
                )
                tensions = {first.tensao, second.tensao}
                connected = len(tensions) == 1 and (
                    shared_endpoint
                    or _has_connection_dot(
                        page,
                        x,
                        y,
                        tensions,
                    )
                )
                project_kind = (
                    f"CRUZAMENTO_{first.tensao}_COM_CONEXAO"
                    if connected and len(tensions) == 1
                    else "CRUZAMENTO_SEM_CONEXAO"
                )
                symbol = (
                    "CRUZAMENTO_COM_CONEXAO"
                    if connected
                    else "CRUZAMENTO_SEM_CONEXAO"
                )
                if any(
                    item.position.page == page_no
                    and math.hypot(
                        item.position.x - x,
                        item.position.y_pdf(page.rect.height) - y,
                    )
                    <= 3.0
                    and item.codigo == symbol
                    for item in result
                ):
                    continue
                result.append(
                    StructureType(
                        codigo=symbol,
                        position=Position.from_pdf(
                            page_no,
                            x,
                            y,
                            page.rect.height,
                        ),
                        project_kind=project_kind,
                        tension="+".join(sorted(tensions)),
                        direction=_direction_for_segment(first),
                        evidence="project_topology_and_vector_node",
                        confidence=0.98 if connected else 0.90,
                    )
                )
    return result


def _pole_structures(extraction: ProjectExtraction) -> list[StructureType]:
    result: list[StructureType] = []
    for pole in extraction.poles:
        page_no = pole.position.page
        page_height = extraction.page_sizes[page_no][1]
        x = pole.position.x
        y = pole.position.y_pdf(page_height)
        page_scale = min(extraction.page_sizes[page_no])
        tolerance = max(5.0, page_scale * 0.009)
        attached = [
            segment
            for segment in extraction.conductors
            if segment.page == page_no
            and point_segment_distance(x, y, segment) <= tolerance
        ]
        for tension in ("MT", "BT"):
            relevant = [segment for segment in attached if segment.tensao == tension]
            if not relevant:
                continue
            interior = [
                segment
                for segment in relevant
                if 0.035 < _projection_parameter(x, y, segment) < 0.965
            ]
            rays: list[tuple[float, float]] = []
            for segment in relevant:
                endpoints = (
                    (segment.x1, segment.y1),
                    (segment.x2, segment.y2),
                )
                for endpoint_x, endpoint_y in endpoints:
                    dx = endpoint_x - x
                    dy = endpoint_y - y
                    length = math.hypot(dx, dy)
                    if length <= tolerance:
                        continue
                    direction = (dx / length, dy / length)
                    if any(
                        direction[0] * old[0] + direction[1] * old[1] > 0.985
                        for old in rays
                    ):
                        continue
                    rays.append(direction)
            straight = any(
                first[0] * second[0] + first[1] * second[1] < -0.86
                for index, first in enumerate(rays)
                for second in rays[index + 1 :]
            )
            if not straight:
                continue
            primary = tension == "MT"
            exact_colors = {
                tuple(round(channel, 3) for channel in segment.color)
                for segment in relevant
            }
            widths = [max(float(segment.width), 0.01) for segment in relevant]
            width_change = (
                max(widths) - min(widths)
                > max(0.18, min(widths) * 0.35)
            )
            verified_style_change = len(exact_colors) > 1 or width_change
            if interior or not verified_style_change:
                project_kind = (
                    "PASSAGEM_CONDUTOR_PRIMARIO"
                    if primary
                    else "PASSAGEM_CONDUTOR_SECUNDARIO"
                )
                symbol = "PASSAGEM_PRIMARIO" if primary else "PASSAGEM_SECUNDARIO"
                confidence = 0.96 if interior else 0.90
            else:
                project_kind = (
                    "ENCABECAMENTO_PRIMARIO"
                    if primary
                    else "ENCABECAMENTO_SECUNDARIO"
                )
                symbol = (
                    "ENCABECAMENTO_PRIMARIO"
                    if primary
                    else "ENCABECAMENTO_SECUNDARIO"
                )
                confidence = 0.88
            result.append(
                StructureType(
                    codigo=symbol,
                    position=pole.position,
                    project_kind=project_kind,
                    tension=tension,
                    direction=_direction_for_segment(relevant[0]),
                    evidence="project_topology",
                    confidence=confidence,
                )
            )
    return result


def detect_project_structures(
    doc: fitz.Document,
    extraction: ProjectExtraction,
) -> list[StructureType]:
    structures = [
        *_crossing_structures(doc, extraction),
        *_pole_structures(extraction),
    ]
    structures.sort(
        key=lambda item: (
            item.position.page,
            item.position.y,
            item.position.x,
            item.codigo,
        )
    )
    return structures
