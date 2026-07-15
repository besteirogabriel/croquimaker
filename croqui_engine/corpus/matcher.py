from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from croqui_engine.corpus.discovery import discover_corpus, sha256_file
from croqui_engine.corpus.registry import load_registry, save_registry


class CorpusProjectMatch(BaseModel):
    case_id: str
    project_pdf_path: str
    project_pdf_name: str
    target_pdf_path: str | None = None
    target_pdf_name: str | None = None
    target_xls_path: str | None = None
    target_xls_name: str | None = None
    equipment_type: str | None = None
    equipment_code: str | None = None
    sha256: str


def find_project_match(pdf_path: Path) -> CorpusProjectMatch | None:
    if not pdf_path.is_file():
        return None
    try:
        registry = load_registry()
    except FileNotFoundError:
        try:
            registry = discover_corpus()
            save_registry(registry)
        except FileNotFoundError:
            return None
    digest = sha256_file(pdf_path)
    for case in registry.cases:
        for project_pdf in case.project_pdfs:
            if project_pdf.sha256 != digest:
                continue
            target_pdf = case.target_croqui_pdfs[0] if case.target_croqui_pdfs else None
            return CorpusProjectMatch(
                case_id=case.case_id,
                project_pdf_path=project_pdf.path,
                project_pdf_name=project_pdf.name,
                target_pdf_path=target_pdf.path if target_pdf else None,
                target_pdf_name=target_pdf.name if target_pdf else None,
                target_xls_path=case.target_croqui_xls.path if case.target_croqui_xls else None,
                target_xls_name=case.target_croqui_xls.name if case.target_croqui_xls else None,
                equipment_type=case.equipment_type_from_name,
                equipment_code=case.equipment_code_from_name,
                sha256=digest,
            )
    return None
