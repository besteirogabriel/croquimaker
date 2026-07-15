from __future__ import annotations

from croqui_engine.core.models import BBox


def collides(a: BBox, b: BBox) -> bool:
    return not (a.x1 < b.x0 or a.x0 > b.x1 or a.y1 < b.y0 or a.y0 > b.y1)

