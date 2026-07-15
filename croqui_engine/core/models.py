from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SerializableModel(BaseModel):
    model_config = {"populate_by_name": True}

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class BBox(SerializableModel):
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


class ExtractedWord(SerializableModel):
    text: str
    page_index: int
    bbox: BBox
    block_no: int | None = None
    line_no: int | None = None
    word_no: int | None = None
    font_size: float | None = None


class TextBlock(SerializableModel):
    text: str
    page_index: int
    bbox: BBox | None = None
    block_no: int | None = None
    kind: str = "text"


class DrawingPrimitive(SerializableModel):
    type: Literal["line", "polyline", "rect", "circle_like", "curve", "unknown"] = "unknown"
    page_index: int
    points: list[tuple[float, float]] = Field(default_factory=list)
    stroke_color: tuple[float, float, float] | None = None
    fill_color: tuple[float, float, float] | None = None
    width: float | None = None
    dash: list[float] | None = None
    bbox: BBox | None = None
    raw_type: str | None = None


class PageInfo(SerializableModel):
    index: int
    width: float
    height: float
    rotation: int = 0
    orientation: str = "portrait"
    kind: str = "UNKNOWN"
    confidence: float = 0.0
    signals: list[str] = Field(default_factory=list)
    thumbnail: str | None = None


class Equipment(SerializableModel):
    code: str
    type: str
    page_index: int | None = None
    bbox: BBox | None = None
    confidence: float = 0.0
    raw_text: str | None = None
    node_id: str | None = None
    status: str | None = None
    approved: bool = False
    deleted: bool = False


class Node(SerializableModel):
    id: str
    type: str = "POSTE"
    x: float | None = None
    y: float | None = None
    page_index: int | None = None
    bbox: BBox | None = None
    confidence: float = 0.0
    raw_text: str | None = None
    approved: bool = False
    deleted: bool = False


class Span(SerializableModel):
    id: str
    from_node: str
    to_node: str
    length_m: float | None = None
    cable: str | None = None
    network_type: str | None = None
    status: str | None = None
    page_index: int | None = None
    bbox: BBox | None = None
    confidence: float = 0.0
    raw_text: str | None = None
    approved: bool = False
    deleted: bool = False


class WorkArea(SerializableModel):
    id: str
    type: str = "AREA_TRABALHO"
    page_index: int
    bbox: BBox | None = None
    confidence: float = 0.0
    raw_text: str | None = None


class MaterialItem(SerializableModel):
    code: str
    source: str | None = None
    page_index: int | None = None
    confidence: float = 0.0


class ValidationMessage(SerializableModel):
    severity: str
    code: str
    message: str
    object_type: str | None = None
    object_id: str | None = None
    suggested_action: str | None = None


class TechnicalPayload(SerializableModel):
    schema_version: str = "0.1"
    engine_version: str = "0.1-local"
    job_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    pages: list[PageInfo] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    spans: list[Span] = Field(default_factory=list)
    equipment: list[Equipment] = Field(default_factory=list)
    work_areas: list[WorkArea] = Field(default_factory=list)
    materials: list[MaterialItem] = Field(default_factory=list)
    validations: list[ValidationMessage] = Field(default_factory=list)
    confidence_global: float = 0.0
    raw_counts: dict[str, int] = Field(default_factory=dict)
    revision_log: list[dict[str, Any]] = Field(default_factory=list)

    def active_equipment(self) -> list[Equipment]:
        return [item for item in self.equipment if not item.deleted]

    def active_nodes(self) -> list[Node]:
        return [item for item in self.nodes if not item.deleted]

    def active_spans(self) -> list[Span]:
        return [item for item in self.spans if not item.deleted]
