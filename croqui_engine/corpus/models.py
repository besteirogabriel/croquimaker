from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CorpusFile(BaseModel):
    path: str
    name: str
    kind: Literal["PROJECT_PDF", "TARGET_CROQUI_PDF", "TARGET_CROQUI_XLS", "OTHER"]
    size_bytes: int
    sha256: str


class GoldenCase(BaseModel):
    case_id: str
    directory: str
    project_pdfs: list[CorpusFile] = Field(default_factory=list)
    target_croqui_pdfs: list[CorpusFile] = Field(default_factory=list)
    target_croqui_xls: CorpusFile | None = None
    other_files: list[CorpusFile] = Field(default_factory=list)
    equipment_type_from_name: str | None = None
    equipment_code_from_name: str | None = None
    status: Literal[
        "COMPLETE",
        "MISSING_TARGET_PDF",
        "MISSING_PROJECT",
        "MISSING_XLS",
        "INVALID",
    ] = "INVALID"
    warnings: list[str] = Field(default_factory=list)


class CorpusRegistry(BaseModel):
    schema_version: str = "2.0-corpus-registry"
    source_path: str
    cases: list[GoldenCase] = Field(default_factory=list)
    total_cases: int = 0
    complete_cases: int = 0
    missing_target_pdf: int = 0
    missing_project: int = 0
    missing_xls: int = 0
    invalid_cases: int = 0
    equipment_type_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def case_map(self) -> dict[str, GoldenCase]:
        return {case.case_id: case for case in self.cases}
