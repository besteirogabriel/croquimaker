from __future__ import annotations

from pydantic import Field

from croqui_engine.core.models import BBox, SerializableModel
from croqui_engine.core.models_v2 import CroquiEntity


class CanvasModel(SerializableModel):
    page_size: tuple[float, float] = (841.68, 595.20)
    drawing_area: BBox | None = None
    entities: list[CroquiEntity] = Field(default_factory=list)

