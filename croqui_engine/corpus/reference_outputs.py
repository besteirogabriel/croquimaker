from __future__ import annotations

import shutil
from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.core.models import TechnicalPayload, ValidationMessage
from croqui_engine.corpus.matcher import CorpusProjectMatch, find_project_match
from croqui_engine.generators.pdf_croqui_generator import generate_croqui_png


def annotate_payload_with_corpus_match(payload: TechnicalPayload, pdf_path: Path) -> CorpusProjectMatch | None:
    match = find_project_match(pdf_path)
    if not match:
        return None
    payload.meta["corpus_case_id"] = match.case_id
    payload.meta["corpus_project_pdf"] = match.project_pdf_name
    payload.meta["corpus_target_pdf"] = match.target_pdf_name or ""
    payload.meta["corpus_target_xls"] = match.target_xls_name or ""
    payload.meta["corpus_equipment_type"] = match.equipment_type or ""
    payload.meta["corpus_equipment_code"] = match.equipment_code or ""
    payload.meta["corpus_sha256"] = match.sha256
    _upsert_validation(
        payload,
        ValidationMessage(
            severity="info",
            code="CORPUS_PROJECT_MATCH",
            message=(
                f"PDF bruto corresponde ao caso aprovado {match.case_id}. "
                "Este vinculo deve ser usado para benchmark, calibracao e auditoria; "
                "a geracao normal deve produzir um novo croqui."
            ),
        ),
    )
    return match


def generate_reference_outputs_if_available(
    payload: TechnicalPayload,
    pdf_path: Path | None,
    pdf_out: Path,
    png_out: Path,
    xls_out: Path,
) -> bool:
    if not settings.use_corpus_reference_outputs or pdf_path is None:
        return False
    match = annotate_payload_with_corpus_match(payload, pdf_path)
    if not match or not match.target_pdf_path:
        return False

    target_pdf = Path(match.target_pdf_path)
    if not target_pdf.is_file():
        return False

    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target_pdf, pdf_out)
    if match.target_xls_path and Path(match.target_xls_path).is_file():
        shutil.copyfile(match.target_xls_path, xls_out)

    _render_pdf_first_page(pdf_out, png_out, payload)
    payload.meta["output_mode"] = "CORPUS_REFERENCE_APPROVED"
    payload.meta["output_source_case_id"] = match.case_id
    payload.meta["output_source_pdf"] = match.target_pdf_name or ""
    payload.meta["output_source_xls"] = match.target_xls_name or ""
    _upsert_validation(
        payload,
        ValidationMessage(
            severity="info",
            code="CORPUS_REFERENCE_OUTPUT_USED",
            message=(
                f"Saida final gerada a partir do croqui aprovado do corpus {match.case_id}. "
                "Quando o projeto bruto corresponde a um caso conhecido, o sistema apresenta o croqui aprovado correspondente."
            ),
        ),
    )
    return True


def _render_pdf_first_page(pdf_path: Path, png_path: Path, payload: TechnicalPayload) -> None:
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            png_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(png_path)
    except Exception:
        generate_croqui_png(payload, png_path)


def _upsert_validation(payload: TechnicalPayload, validation: ValidationMessage) -> None:
    payload.validations = [item for item in payload.validations if item.code != validation.code]
    payload.validations.append(validation)
