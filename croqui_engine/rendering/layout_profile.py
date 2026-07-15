from __future__ import annotations

from croqui_engine.core.models import BBox, SerializableModel


class LayoutProfile(SerializableModel):
    name: str = "corpus-a4-landscape"
    page_size: tuple[float, float] = (841.68, 595.20)
    header_area: BBox = BBox(x0=0, y0=0, x1=841.68, y1=90)
    drawing_area: BBox = BBox(x0=24, y0=92, x1=817, y1=430)
    viability_area: BBox = BBox(x0=24, y0=432, x1=817, y1=575)


def default_layout_profile() -> LayoutProfile:
    return LayoutProfile()

