from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from werkzeug.datastructures import FileStorage

from croqui_engine.app.output_summary import load_validation_report, output_summary
from croqui_engine.core.cities import normalize_city_group
from croqui_engine.core.enums import JobStatus
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.pipeline import generate_outputs, process_pdf
from croqui_engine.generators.json_exporter import load_payload_json
from croqui_engine.storage.database import Job
from croqui_engine.storage.file_store import job_output_dir, new_job_id, save_uploaded_pdf
from croqui_engine.storage.repositories import JobRepository


@dataclass
class ProjectProcessingResult:
    job: Job
    payload: TechnicalPayload
    outputs: dict[str, Path]
    validation_report: dict | None
    summary: dict


def process_project_upload(
    file: FileStorage,
    *,
    created_by: str,
    city_group: str,
    notes: str = "",
) -> ProjectProcessingResult:
    jobs = JobRepository()
    job_id = new_job_id()
    pdf_path = save_uploaded_pdf(file, job_id)
    job = Job(
        id=job_id,
        filename=file.filename or "projeto.pdf",
        original_pdf_path=str(pdf_path),
        status=JobStatus.UPLOADED.value,
        message="PDF salvo localmente.",
        notes=notes,
        created_by=created_by,
        city_group=normalize_city_group(city_group, fallback="caxias_do_sul"),
    )
    jobs.create(job)
    try:
        jobs.update(job_id, status=JobStatus.EXTRACTING.value, message="Processamento output-first em andamento.")
        payload = process_pdf(pdf_path, job_id)
        jobs.update(job_id, status=JobStatus.GENERATING.value, message="Gerando PDF, Excel e relatorio.")
        outputs = generate_outputs(payload, pdf_path)
        final_payload = _load_final_payload(outputs, payload)
        report = load_validation_report(job_id)
        summary = output_summary(final_payload, report)
        status, message = _status_for_summary(summary)
        city = normalize_city_group(
            str(final_payload.meta.get("municipality") or ""),
            fallback=normalize_city_group(city_group, fallback="caxias_do_sul"),
        )
        job = jobs.update(
            job_id,
            status=status,
            message=message,
            tes_number=str(final_payload.meta.get("tes_number", "")),
            municipality=str(final_payload.meta.get("municipality", "")),
            confidence=_confidence_for_summary(final_payload, summary),
            payload_path=str(job_output_dir(job_id) / "technical_payload.json"),
            reviewed_payload_path=str(outputs.get("json", "")),
            croqui_pdf_path=str(outputs.get("pdf", "")),
            croqui_png_path=str(outputs.get("png", "")),
            excel_path=str(outputs.get("xls", "")),
            city_group=city,
        )
        assert job is not None
        return ProjectProcessingResult(job, final_payload, outputs, report, summary)
    except Exception:
        jobs.update(job_id, status=JobStatus.FAILED.value, message="Falha no processamento output-first.")
        raise


def _load_final_payload(outputs: dict[str, Path], fallback: TechnicalPayload) -> TechnicalPayload:
    json_path = outputs.get("json")
    if json_path and json_path.is_file():
        try:
            return load_payload_json(json_path)
        except Exception:
            return fallback
    return fallback


def _status_for_summary(summary: dict) -> tuple[str, str]:
    output_status = str(summary.get("output_status") or "").lower()
    validation_status = str(summary.get("validation_status") or "").upper()
    if validation_status == "BLOCKED" or output_status == "blocked":
        return JobStatus.NEEDS_REVIEW.value, "Saida bloqueada. Revise erros antes de homologar."
    if output_status == "final_candidate":
        return JobStatus.DONE.value, "Candidato final gerado pelo pipeline output-first."
    return JobStatus.NEEDS_REVIEW.value, "Rascunho gerado para revisao pelo pipeline output-first."


def _confidence_for_summary(payload: TechnicalPayload, summary: dict) -> float:
    selected = summary.get("selected_equipment_confidence")
    focus = summary.get("focus_confidence")
    values = [float(value) for value in (selected, focus) if value is not None]
    if values:
        return round(sum(values) / len(values), 3)
    return payload.confidence_global
