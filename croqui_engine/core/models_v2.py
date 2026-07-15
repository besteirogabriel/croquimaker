from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from croqui_engine.core.models import BBox, SerializableModel, TechnicalPayload
from croqui_engine.core.schema_version import V2_PROJECT_SCHEMA_VERSION


class EvidenceRef(SerializableModel):
    source: Literal["PROJECT_PDF", "TARGET_PDF", "TARGET_XLS", "SYMBOL_CATALOG", "MANUAL"]
    case_id: str | None = None
    file_path: str | None = None
    page_index: int | None = None
    sheet_name: str | None = None
    cell_ref: str | None = None
    bbox: BBox | None = None
    text: str | None = None
    confidence: float = 1.0


class CroquiEntity(SerializableModel):
    id: str
    type: str
    code: str | None = None
    label: str | None = None
    bbox: BBox | None = None
    geometry: dict[str, Any] | None = None
    style: dict[str, Any] | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class TechnicalPayloadV2(SerializableModel):
    schema_version: str = V2_PROJECT_SCHEMA_VERSION
    engine_version: str = "0.2-local-v2"
    job_id: str | None = None
    case_id: str | None = None
    v1_payload: TechnicalPayload | None = None
    project_entities: list[CroquiEntity] = Field(default_factory=list)
    graph_entities: list[CroquiEntity] = Field(default_factory=list)
    target_case_id: str | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class GenerationComparison(SerializableModel):
    schema_version: str = "2.0-comparison"
    case_id: str
    visual_score: float = 0.0
    text_score: float = 0.0
    geometry_score: float = 0.0
    equipment_score: float = 0.0
    excel_score: float = 0.0
    acceptance_level: str = "BLOCKED"
    generated_pdf_path: str | None = None
    target_pdf_path: str | None = None
    visual_diff_path: str | None = None
    blocking_differences: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class CaseRunResult(BaseModel):
    case_id: str
    ok: bool
    generated_pdf_path: str | None = None
    comparison_path: str | None = None
    error: str | None = None

