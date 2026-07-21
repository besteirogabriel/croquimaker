from __future__ import annotations

import math
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
        for index, (x, y) in enumerate(accepted, start=1):
            poles.append(
                Pole(
                    codigo=f"P{index}",
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
