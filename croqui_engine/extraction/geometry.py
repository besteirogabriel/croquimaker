from __future__ import annotations

import math

from croqui_engine.core.models import BBox, ExtractedWord


def bbox_center(bbox: BBox) -> tuple[float, float]:
    return bbox.center


def distance_points(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def distance_bbox_to_point(bbox: BBox, point: tuple[float, float]) -> float:
    return distance_points(bbox.center, point)


def pdf_to_image_point(x: float, y: float, dpi: int = 150) -> tuple[float, float]:
    scale = dpi / 72.0
    return x * scale, y * scale


def find_nearest_words(
    target_bbox: BBox, words: list[ExtractedWord], radius: float = 120
) -> list[ExtractedWord]:
    center = target_bbox.center
    found = [
        word for word in words if distance_points(center, word.bbox.center) <= radius
    ]
    return sorted(found, key=lambda word: distance_points(center, word.bbox.center))
