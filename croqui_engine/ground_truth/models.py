from __future__ import annotations

from typing import Any

from pydantic import Field

from croqui_engine.core.models import BBox, SerializableModel
from croqui_engine.core.models_v2 import CroquiEntity
from croqui_engine.core.schema_version import V2_TARGET_SCHEMA_VERSION


class XlsSheetProfile(SerializableModel):
    name: str
    nrows: int
    ncols: int
    non_empty_cells: int
    merged_cells: list[tuple[int, int, int, int]] = Field(default_factory=list)
    cells: list[dict[str, Any]] = Field(default_factory=list)


class TargetCroquiPayload(SerializableModel):
    schema_version: str = V2_TARGET_SCHEMA_VERSION
    case_id: str
    page_size: tuple[float, float] = (0.0, 0.0)
    header_fields: dict[str, str] = Field(default_factory=dict)
    drawing_area: BBox | None = None
    viability_table: dict[str, Any] = Field(default_factory=dict)
    texts: list[CroquiEntity] = Field(default_factory=list)
    symbols: list[CroquiEntity] = Field(default_factory=list)
    lines: list[CroquiEntity] = Field(default_factory=list)
    areas: list[CroquiEntity] = Field(default_factory=list)
    xls_profile: dict[str, Any] = Field(default_factory=dict)
    extracted_from_pdf: bool = False
    extracted_from_xls: bool = False
    warnings: list[str] = Field(default_factory=list)

