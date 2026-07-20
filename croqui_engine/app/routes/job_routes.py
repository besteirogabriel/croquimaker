from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from croqui_engine.app.auth import user_can_edit_job, user_can_generate_job
from croqui_engine.app.output_summary import (
    artifact_summary,
    load_validation_report,
    output_summary,
)
from croqui_engine.app.project_processing import process_project_upload
from croqui_engine.core.cities import (
    CITY_GROUP_LABELS,
    PUBLIC_CITY_GROUPS,
    city_group_label,
    normalize_city_group,
)
from croqui_engine.core.config import settings
from croqui_engine.core.enums import JobStatus
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.pipeline import generate_outputs
from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import benchmark_latest_dir
from croqui_engine.generators.dependency_report_generator import generate_dependency_report
from croqui_engine.generators.json_exporter import load_payload_json
from croqui_engine.storage.database import Job
from croqui_engine.storage.file_store import (
    job_output_dir,
    zip_directory,
)
from croqui_engine.storage.repositories import JobRepository

bp = Blueprint("jobs", __name__)
jobs = JobRepository()


@bp.route("/dashboard")
@login_required
def dashboard():
    recent = jobs.list_recent()
    city_stats = {city: jobs.dashboard_stats(city) for city in PUBLIC_CITY_GROUPS}
    jobs_by_city = {city: jobs.list_recent(12, city) for city in PUBLIC_CITY_GROUPS}
    return render_template(
        "dashboard.html",
        jobs=recent,
        stats=jobs.dashboard_stats(),
        city_stats=city_stats,
        jobs_by_city=jobs_by_city,
        city_labels=CITY_GROUP_LABELS,
        selected_city=None,
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("pdf")
        if not file or not file.filename:
            flash("Selecione um PDF.", "error")
            return redirect(url_for("jobs.upload"))
        try:
            result = process_project_upload(
                file,
                created_by=current_user.email,
                city_group=getattr(current_user, "city_group", ""),
                notes=request.form.get("notes", ""),
            )
            flash("PDF processado pelo fluxo output-first.", "success")
            return redirect(url_for("croqui_editor", job_id=result.job.id))
        except Exception as exc:
            flash(f"Falha no processamento: {exc}", "error")
            return redirect(url_for("jobs.dashboard"))
    return render_template("upload.html")


@bp.route("/jobs")
@login_required
def job_list():
    return render_template(
        "dashboard.html",
        jobs=jobs.list_recent(),
        stats=jobs.dashboard_stats(),
        city_stats={city: jobs.dashboard_stats(city) for city in PUBLIC_CITY_GROUPS},
        jobs_by_city=None,
        city_labels=CITY_GROUP_LABELS,
        selected_city=None,
    )


@bp.route("/jobs/cidade/<city_group>")
@login_required
def city_jobs(city_group: str):
    city = normalize_city_group(city_group)
    return render_template(
        "dashboard.html",
        jobs=jobs.list_recent(100, city),
        stats=jobs.dashboard_stats(city),
        city_stats={city: jobs.dashboard_stats(city) for city in PUBLIC_CITY_GROUPS},
        jobs_by_city=None,
        city_labels=CITY_GROUP_LABELS,
        selected_city=city,
    )


@bp.route("/jobs/<job_id>")
@login_required
def job_detail(job_id: str):
    job = _get_job(job_id)
    payload = _load_payload(job)
    report = load_validation_report(job_id)
    summary = output_summary(payload, report)
    artifacts = artifact_summary(job)
    return render_template(
        "job_detail.html",
        job=job,
        payload=payload,
        output_summary=summary,
        validation_report=report,
        artifacts=artifacts,
        can_edit=user_can_edit_job(job),
        can_generate=user_can_generate_job(job),
        city_label=city_group_label(job.city_group),
    )


@bp.route("/jobs/<job_id>/review")
@login_required
def review(job_id: str):
    job = _get_job(job_id)
    payload = _load_payload(job)
    overlays = []
    overlays_dir = job_output_dir(job_id) / "overlays"
    if overlays_dir.exists():
        overlays = sorted(overlays_dir.glob("*.png"))
    return render_template(
        "review.html",
        job=job,
        payload=payload,
        overlays=overlays,
        can_edit=user_can_edit_job(job),
        can_generate=user_can_generate_job(job),
        city_label=city_group_label(job.city_group),
    )


@bp.route("/settings")
@login_required
def settings_page():
    from croqui_engine.symbols.catalog import load_symbol_catalog

    catalog = load_symbol_catalog()
    return render_template("settings.html", catalog=catalog, settings=settings)


@bp.route("/admin/corpus")
@login_required
def admin_corpus():
    if not settings.show_training_tools:
        abort(404)
    try:
        registry = load_registry()
    except FileNotFoundError:
        registry = None
    query = request.args.get("q", "").strip().lower()
    kind = request.args.get("type", "").strip().upper()
    cases = registry.cases if registry else []
    if query:
        cases = [
            case
            for case in cases
            if query in case.case_id.lower()
            or query in str(case.equipment_code_from_name or "").lower()
            or any(query in file.name.lower() for file in [*case.project_pdfs, *case.target_croqui_pdfs])
        ]
    if kind:
        cases = [case for case in cases if (case.equipment_type_from_name or "") == kind]
    return render_template("admin_corpus.html", registry=registry, cases=cases[:300], query=query, kind=kind)


@bp.route("/admin/corpus/<case_id>")
@login_required
def admin_corpus_detail(case_id: str):
    if not settings.show_training_tools:
        abort(404)
    registry = load_registry()
    case = registry.case_map().get(case_id)
    if not case:
        abort(404)
    gt_path = settings.root_dir / "data" / "corpus" / "ground_truth" / case_id / "target_payload.json"
    target_summary = None
    if gt_path.exists():
        target_summary = json.loads(gt_path.read_text(encoding="utf-8"))
    return render_template("admin_corpus_detail.html", case=case, target_summary=target_summary)


@bp.route("/admin/corpus/<case_id>/compare")
@login_required
def admin_corpus_compare(case_id: str):
    if not settings.show_training_tools:
        abort(404)
    case_dir = benchmark_latest_dir() / "cases" / case_id
    comparison = None
    path = case_dir / "comparison.json"
    if path.exists():
        comparison = json.loads(path.read_text(encoding="utf-8"))
    image_files = [
        {"label": "PDF aprovado", "filename": "target_page.png", "exists": (case_dir / "target_page.png").exists()},
        {"label": "PDF gerado", "filename": "generated_page.png", "exists": (case_dir / "generated_page.png").exists()},
        {"label": "Diferencas", "filename": "visual_diff.png", "exists": (case_dir / "visual_diff.png").exists()},
    ]
    return render_template(
        "admin_corpus_compare.html",
        case_id=case_id,
        comparison=comparison,
        image_files=image_files,
    )


@bp.route("/admin/benchmark/files/<case_id>/<filename>")
@login_required
def benchmark_case_file(case_id: str, filename: str):
    if not settings.show_training_tools:
        abort(404)
    if filename not in {"target_page.png", "generated_page.png", "visual_diff.png", "comparison.json"}:
        abort(404)
    path = benchmark_latest_dir() / "cases" / case_id / filename
    if not path.is_file():
        abort(404)
    return send_file(path)


@bp.route("/admin/symbols")
@login_required
def admin_symbols():
    static_dir = settings.root_dir / "croqui_engine" / "app" / "static"
    preferred = [
        "img/simbologia_oficial_extraida.svg",
        "img/simbologia_oficial_extraida_p2.svg",
    ]
    symbol_images = [item for item in preferred if (static_dir / item).exists()]
    if not symbol_images:
        symbol_images = ["img/simbologia_oficial.svg"]
    return render_template(
        "admin_symbols.html",
        symbol_images=symbol_images,
    )


@bp.route("/admin/symbols/rendered/<case_id>/<filename>")
@login_required
def admin_symbol_rendered_file(case_id: str, filename: str):
    abort(404)


@bp.route("/admin/benchmark")
@login_required
def admin_benchmark():
    if not settings.show_training_tools:
        abort(404)
    summary_path = benchmark_latest_dir() / "benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    return render_template("admin_benchmark.html", summary=summary)


@bp.route("/reports/dependencies")
@login_required
def dependency_report():
    path = generate_dependency_report()
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.route("/jobs/<job_id>/download/<kind>")
@login_required
def download(job_id: str, kind: str):
    job = _get_job(job_id)
    valid_kinds = {"json", "pdf", "png", "svg", "xls", "report", "overlays"}
    if kind not in valid_kinds:
        abort(404)

    paths = {
        "json": job.reviewed_payload_path or job.payload_path,
        "pdf": job.croqui_pdf_path,
        "png": job.croqui_png_path,
        "svg": str(job_output_dir(job_id) / "croqui_final.svg"),
        "xls": job.excel_path,
        "report": str(job_output_dir(job_id) / "output_validation_report.json"),
    }
    if kind == "overlays":
        zip_path = job_output_dir(job_id) / "overlays.zip"
        zip_directory(job_output_dir(job_id) / "overlays", zip_path)
        return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

    raw_path = paths.get(kind) or ""
    path = Path(raw_path) if raw_path else None
    if kind in {"pdf", "png", "svg", "xls"} and user_can_generate_job(job):
        payload_path = Path(job.reviewed_payload_path or job.payload_path or "")
        if payload_path.is_file():
            try:
                payload = load_payload_json(payload_path)
                outputs = _generate_for_job(job, payload)
                path = outputs.get(kind)
            except Exception as exc:
                flash(f"Nao foi possivel gerar a saida solicitada: {exc}", "error")
                return redirect(url_for("jobs.job_detail", job_id=job_id))

    if (path is None or not path.is_file()) and kind in {"pdf", "png", "svg", "xls"}:
        if not user_can_generate_job(job):
            flash("Esta saida ainda nao foi gerada para este job.", "error")
            return redirect(url_for("jobs.job_detail", job_id=job_id))
        payload_path = Path(job.reviewed_payload_path or job.payload_path or "")
        if payload_path.is_file():
            try:
                payload = load_payload_json(payload_path)
                outputs = _generate_for_job(job, payload)
                path = outputs.get(kind)
            except Exception as exc:
                flash(f"Nao foi possivel gerar a saida solicitada: {exc}", "error")
                return redirect(url_for("jobs.job_detail", job_id=job_id))

    if path is None or not path.is_file():
        flash("Arquivo ainda nao disponivel para este job.", "error")
        return redirect(url_for("jobs.job_detail", job_id=job_id))
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.route("/jobs/<job_id>/preview.png")
@login_required
def preview_png(job_id: str):
    job = _get_job(job_id)
    path = Path(job.croqui_png_path or "")
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/png")


@bp.route("/outputs/<job_id>/overlays/<filename>")
@login_required
def overlay_file(job_id: str, filename: str):
    path = job_output_dir(job_id) / "overlays" / filename
    if not path.exists():
        abort(404)
    return send_file(path)


def _get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if not job:
        abort(404)
    return job


def _load_payload(job: Job) -> TechnicalPayload:
    path = Path(job.reviewed_payload_path or job.payload_path or "")
    if path.exists():
        return load_payload_json(path)
    return TechnicalPayload(job_id=job.id)


def _generate_for_job(job: Job, payload: TechnicalPayload) -> dict:
    outputs = generate_outputs(payload, Path(job.original_pdf_path))
    report = load_validation_report(job.id)
    summary = output_summary(payload, report)
    status, message = _status_for_output_summary(summary)
    city_group = _city_group_for_payload(payload, job.city_group)
    jobs.update(
        job.id,
        status=status,
        message=message,
        reviewed_payload_path=str(outputs["json"]),
        croqui_pdf_path=str(outputs["pdf"]),
        croqui_png_path=str(outputs["png"]),
        excel_path=str(outputs["xls"]),
        confidence=payload.confidence_global,
        city_group=city_group,
    )
    return outputs


def _status_for_output_summary(summary: dict) -> tuple[str, str]:
    output_status = str(summary.get("output_status") or "").lower()
    validation_status = str(summary.get("validation_status") or "").upper()
    if validation_status == "BLOCKED" or output_status == "blocked":
        return JobStatus.NEEDS_REVIEW.value, "Saida bloqueada. Revise erros antes de homologar."
    if output_status == "final_candidate":
        return JobStatus.DONE.value, "Candidato final gerado pelo pipeline output-first."
    return JobStatus.NEEDS_REVIEW.value, "Rascunho gerado para revisao pelo pipeline output-first."


def _city_group_for_payload(payload: TechnicalPayload, fallback: str | None = None) -> str:
    return normalize_city_group(
        str(payload.meta.get("municipality") or ""),
        fallback=normalize_city_group(fallback, fallback="caxias_do_sul"),
    )


def _public_symbols(symbols: list[dict]) -> list[dict]:
    return [
        {
            "id": symbol.get("id", ""),
            "names": symbol.get("names", []),
            "text_patterns": symbol.get("text_patterns", []),
        }
        for symbol in symbols
    ]


def _public_materials(materials: list[dict]) -> list[dict]:
    return [{"code": item.get("code", "")} for item in materials]


def _public_line_styles(line_styles: list[dict]) -> list[dict]:
    return [{"description": item.get("description", "")} for item in line_styles]
