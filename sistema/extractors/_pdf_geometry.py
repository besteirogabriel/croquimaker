from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz

from sistema.parsing.entities import ConductorSegment, Pole, Position


@dataclass(frozen=True)
class ConductorColorConfig:
    mt_blue_min: float = 0.85
    mt_green_max: float = 0.20
    bt_green_min: float = 0.55
    bt_blue_max: float = 0.20
    red_max: float = 0.12


DEFAULT_COLOR_CONFIG = ConductorColorConfig()


def normalize_rgb(color) -> tuple[float, float, float] | None:
    if color is None or len(color) < 3:
        return None
    values = tuple(float(v) for v in color[:3])
    if max(values) > 1.0:
        values = tuple(v / 255.0 for v in values)
    return tuple(max(0.0, min(1.0, v)) for v in values)


def classify_conductor_color(color, config: ConductorColorConfig = DEFAULT_COLOR_CONFIG) -> str | None:
    """Classifica somente as cores CAD comprovadas de condutores.

    O limite exclui o ciano dos ramais de consumidor e os tons escuros usados
    em simbolos. O inventario permite calibrar os limites sem aceitar linhas
    pretas, cinzas, marrons, vermelhas ou magenta.
    """

    rgb = normalize_rgb(color)
    if rgb is None:
        return None
    red, green, blue = rgb
    if red <= config.red_max and blue >= config.mt_blue_min and green <= config.mt_green_max:
        return "MT"
    if red <= config.red_max and green >= config.bt_green_min and blue <= config.bt_blue_max:
        return "BT"
    return None


def extract_conductor_segments(doc: fitz.Document) -> tuple[list[ConductorSegment], list[dict]]:
    segments: list[ConductorSegment] = []
    inventory: dict[tuple[int, tuple[float, float, float] | None], dict] = {}

    for page_no, page in enumerate(doc):
        for drawing_no, drawing in enumerate(page.get_drawings()):
            rgb = normalize_rgb(drawing.get("color"))
            key = (page_no, rgb)
            row = inventory.setdefault(
                key,
                {
                    "page": page_no,
                    "color": list(rgb) if rgb else None,
                    "drawings": 0,
                    "segments": 0,
                    "length": 0.0,
                    "types": {},
                    "examples": [],
                },
            )
            row["drawings"] += 1
            dtype = str(drawing.get("type"))
            row["types"][dtype] = row["types"].get(dtype, 0) + 1
            tensao = classify_conductor_color(rgb)
            if drawing.get("type") not in ("s", "fs"):
                tensao = None

            sequence = 0
            for item in drawing.get("items", []):
                if item[0] != "l":
                    continue
                p1, p2 = item[1], item[2]
                length = math.hypot(p2.x - p1.x, p2.y - p1.y)
                row["segments"] += 1
                row["length"] += length
                if len(row["examples"]) < 3:
                    row["examples"].append(
                        [round(p1.x, 3), round(p1.y, 3), round(p2.x, 3), round(p2.y, 3)]
                    )
                if tensao and length > 0.1:
                    segments.append(
                        ConductorSegment(
                            page=page_no,
                            tensao=tensao,
                            x1=float(p1.x),
                            y1=float(p1.y),
                            x2=float(p2.x),
                            y2=float(p2.y),
                            path_id=f"p{page_no}-d{drawing_no}",
                            sequence=sequence,
                            color=rgb or (0.0, 0.0, 0.0),
                            width=float(drawing.get("width") or 0.0),
                        )
                    )
                    sequence += 1

    rows = list(inventory.values())
    for row in rows:
        row["length"] = round(row["length"], 3)
    rows.sort(key=lambda row: row["length"], reverse=True)
    return segments, rows


def point_segment_distance(x: float, y: float, segment: ConductorSegment) -> float:
    vx = segment.x2 - segment.x1
    vy = segment.y2 - segment.y1
    denom = vx * vx + vy * vy
    if denom <= 1e-9:
        return math.hypot(x - segment.x1, y - segment.y1)
    t = ((x - segment.x1) * vx + (y - segment.y1) * vy) / denom
    t = max(0.0, min(1.0, t))
    px = segment.x1 + t * vx
    py = segment.y1 + t * vy
    return math.hypot(x - px, y - py)


def _is_pole_symbol_color(color) -> bool:
    rgb = normalize_rgb(color)
    if rgb is None:
        return False
    return math.dist(rgb, (0.398, 0.066, 0.0)) <= 0.055


def _cluster_points(points: Iterable[tuple[float, float]], radius: float = 8.0) -> list[list[tuple[float, float]]]:
    clusters: list[list[tuple[float, float]]] = []
    for point in points:
        for cluster in clusters:
            cx = sum(p[0] for p in cluster) / len(cluster)
            cy = sum(p[1] for p in cluster) / len(cluster)
            if math.hypot(point[0] - cx, point[1] - cy) <= radius:
                cluster.append(point)
                break
        else:
            clusters.append([point])
    return clusters


def _explicit_node_labels(page: fitz.Page) -> list[tuple[str, float, float]]:
    """Return explicit P-number labels with their PDF-space text positions."""

    labels: dict[str, tuple[str, float, float]] = {}
    for word in page.get_text("words"):
        token = re.sub(r"[^A-Za-z0-9]", "", str(word[4])).upper()
        match = re.fullmatch(r"P0*(\d{1,3})", token)
        if not match:
            continue
        code = f"P{int(match.group(1))}"
        x = (float(word[0]) + float(word[2])) / 2
        y = (float(word[1]) + float(word[3])) / 2
        labels.setdefault(code, (code, x, y))
    return list(labels.values())


def _name_detected_poles(
    page: fitz.Page, accepted: list[tuple[float, float]]
) -> list[tuple[str, float, float]]:
    """Associate real P# labels to detected symbols without inventing node IDs.

    CAD labels are often offset from the pole by a structure-description block,
    so association uses a bounded nearest-neighbour match. Unlabelled symbols get
    an internal AUTO identifier and can still be rendered, but they cannot be
    mistaken for a semantic P# returned by the interpreter.
    """

    labels = _explicit_node_labels(page)
    max_distance = min(page.rect.width, page.rect.height) * 0.18
    candidates: list[tuple[float, str, int]] = []
    for code, lx, ly in labels:
        for index, (px, py) in enumerate(accepted):
            distance = math.hypot(px - lx, py - ly)
            if distance <= max_distance:
                candidates.append((distance, code, index))

    assigned_codes: set[str] = set()
    assigned_indexes: set[int] = set()
    names: dict[int, str] = {}
    for _, code, index in sorted(candidates):
        if code in assigned_codes or index in assigned_indexes:
            continue
        names[index] = code
        assigned_codes.add(code)
        assigned_indexes.add(index)

    result = []
    auto_index = 1
    for index, (x, y) in enumerate(accepted):
        code = names.get(index)
        if code is None:
            code = f"AUTO{auto_index}"
            auto_index += 1
        result.append((code, x, y))
    return result


def detect_poles(doc: fitz.Document, segments: list[ConductorSegment]) -> list[Pole]:
    """Detecta o marcador CAD repetido de poste e o confirma pela rede."""

    candidates: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for page_no, page in enumerate(doc):
        for drawing in page.get_drawings():
            if not _is_pole_symbol_color(drawing.get("color")):
                continue
            rect = drawing.get("rect")
            if rect is None:
                continue
            if not (2.0 <= rect.width <= 16.0 and 2.0 <= rect.height <= 16.0):
                continue
            if len(drawing.get("items", [])) < 18:
                continue
            candidates[page_no].append(((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2))

    poles: list[Pole] = []
    for page_no, points in candidates.items():
        page_height = doc[page_no].rect.height
        page_segments = [segment for segment in segments if segment.page == page_no]
        accepted: list[tuple[float, float]] = []
        for cluster in _cluster_points(points):
            if len(cluster) < 2:
                continue
            x = sum(p[0] for p in cluster) / len(cluster)
            y = sum(p[1] for p in cluster) / len(cluster)
            if page_segments and min(point_segment_distance(x, y, s) for s in page_segments) > 14.0:
                continue
            if any(math.hypot(x - px, y - py) < 5.0 for px, py in accepted):
                continue
            accepted.append((x, y))
        accepted.sort(key=lambda p: (p[1], p[0]))
        for code, x, y in _name_detected_poles(doc[page_no], accepted):
            poles.append(
                Pole(
                    codigo=code,
                    position=Position.from_pdf(page_no, x, y, page_height),
                )
            )
    return poles


def nearest_pole(
    poles: list[Pole], page: int, x: float, y_top: float, page_height: float, max_distance: float = 120.0
) -> tuple[Pole | None, float]:
    best: Pole | None = None
    best_distance = max_distance
    for pole in poles:
        if pole.position.page != page:
            continue
        py = pole.position.y_pdf(page_height)
        distance = math.hypot(pole.position.x - x, py - y_top)
        if distance < best_distance:
            best = pole
            best_distance = distance
    return best, best_distance
