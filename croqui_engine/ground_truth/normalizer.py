from __future__ import annotations

from croqui_engine.core.models import BBox


def normalize_bbox(bbox: BBox | None, page_size: tuple[float, float]) -> dict | None:
    if bbox is None:
        return None
    width, height = page_size
    if width <= 0 or height <= 0:
        return bbox.as_dict()
    return {
        "x0": bbox.x0 / width,
        "y0": bbox.y0 / height,
        "x1": bbox.x1 / width,
        "y1": bbox.y1 / height,
    }

