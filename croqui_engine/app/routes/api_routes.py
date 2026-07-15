from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from croqui_engine.app.auth import user_can_edit_job, user_can_generate_job
from croqui_engine.app.output_summary import (
    artifact_paths,
    artifact_summary,
    load_validation_report,
    output_summary,
)
from croqui_engine.app.project_processing import process_project_upload
from croqui_engine.core.cities import normalize_city_group
from croqui_engine.core.enums import JobStatus
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.pipeline import ensure_output_contract, generate_outputs
from croqui_engine.generators.json_exporter import export_payload_json, load_payload_json
from croqui_engine.generators.svg_graph_exporter import export_from_croqui_graph_svg
from croqui_engine.graph.croqui_graph import CroquiGraph, croqui_graph_from_payload
from croqui_engine.storage.file_store import job_output_dir, write_json
from croqui_engine.storage.repositories import JobRepository, UserRepository
from croqui_engine.topology.graph_builder import build_graph
from croqui_engine.topology.graph_validator import validate_graph

bp = Blueprint("api", __name__, url_prefix="/api")
jobs = JobRepository()


@bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = str(data.get("email") or "").lower().strip()
    password = str(data.get("password") or "")
    user = UserRepository().get_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({"ok": True, "user": _public_user(user)})
    return jsonify({"ok": False, "error": "Credenciais invalidas."}), 401


@bp.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})


@bp.route("/auth/session")
def api_session():
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "user": _public_user(current_user)})
    return jsonify({"authenticated": False, "user": None})


@bp.route("/projects/upload", methods=["POST"])
@login_required
def upload_project():
    file = request.files.get("pdf")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "PDF nao enviado."}), 400
    result = process_project_upload(
        file,
        created_by=current_user.email,
        city_group=getattr(current_user, "city_group", ""),
        notes=request.form.get("notes", ""),
    )
    return jsonify(
        {
            "ok": True,
            "job_id": result.job.id,
            "status": result.job.status,
            "message": result.job.message,
            "summary": result.summary,
            "artifacts": _artifact_links(result.job),
        }
    )


@bp.route("/projects/<job_id>/extract-graph", methods=["POST"])
@login_required
def extract_project_graph(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    if not user_can_edit_job(job):
        abort(403)
    payload = _load_job_payload(job)
    graph = _build_and_store_graph(job_id, payload, Path(job.original_pdf_path))
    jobs.update(job_id, status=JobStatus.NEEDS_REVIEW.value, message="CroquiGraph atualizado para editor.")
    return jsonify({"ok": True, "job_id": job_id, "graph": graph.as_dict()})


@bp.route("/projects/<job_id>/graph")
@login_required
def get_project_graph(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    graph_path = _graph_path(job_id)
    if graph_path.exists():
        import json

        return jsonify(json.loads(graph_path.read_text(encoding="utf-8")))
    payload = _load_job_payload(job)
    graph = _build_and_store_graph(job_id, payload, Path(job.original_pdf_path))
    return jsonify(graph.as_dict())


@bp.route("/projects/<job_id>/export", methods=["POST"])
@login_required
def export_project_graph(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    if not user_can_generate_job(job):
        abort(403)
    data = request.get_json(force=True)
    graph = CroquiGraph.model_validate(data.get("graph") or {})
    graph.id = job_id
    svg = str(data.get("svg") or "")
    outputs = export_from_croqui_graph_svg(graph, svg, job_output_dir(job_id))
    report = load_validation_report(job_id)
    output_status = str((report or {}).get("validation", {}).get("output_status") or "").lower()
    validation_status = str((report or {}).get("validation", {}).get("status") or "").upper()
    status = JobStatus.DONE.value if output_status == "final_candidate" else JobStatus.NEEDS_REVIEW.value
    if validation_status == "BLOCKED" or output_status == "blocked":
        status = JobStatus.NEEDS_REVIEW.value
    message = (
        "PDF/XLS exportados a partir do SVG do editor."
        if status == JobStatus.DONE.value
        else "Exportacao gerada como rascunho/revisao a partir do SVG do editor."
    )
    jobs.update(
        job_id,
        status=status,
        message=message,
        croqui_pdf_path=str(outputs["pdf"]),
        croqui_png_path=str(outputs["png"]),
        excel_path=str(outputs["xlsx"]),
    )
    return jsonify(
        {
            "ok": True,
            "outputs": {key: str(value) for key, value in outputs.items()},
            "validation_report": report,
            "artifacts": _artifact_links(jobs.get(job_id)),
        }
    )


@bp.route("/jobs/<job_id>")
@login_required
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    payload = _load_job_payload(job)
    report = load_validation_report(job_id)
    return jsonify(
        {
            "job_id": job.id,
            "filename": job.filename,
            "status": job.status,
            "message": job.message,
            "summary": output_summary(payload, report),
            "validation_report": report,
            "artifacts": _artifact_links(job),
        }
    )


@bp.route("/jobs/<job_id>/artifacts")
@login_required
def job_artifacts(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    return jsonify({"job_id": job.id, "artifacts": _artifact_links(job)})


@bp.route("/jobs/<job_id>/download/<kind>")
@login_required
def download_artifact(job_id: str, kind: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    aliases = {"excel": "xls", "xlsx": "xls"}
    kind = aliases.get(kind, kind)
    paths = artifact_paths(job)
    path = paths.get(kind)
    if path is None or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.route("/jobs/<job_id>/payload")
@login_required
def get_payload(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    path = Path(job.reviewed_payload_path or job.payload_path or "")
    if not path.exists():
        return jsonify({})
    return jsonify(load_payload_json(path).as_dict())


@bp.route("/jobs/<job_id>/payload/update", methods=["POST"])
@login_required
def update_payload(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    if not user_can_edit_job(job):
        abort(403)
    data = request.get_json(force=True)
    payload = TechnicalPayload.model_validate(data)
    payload.job_id = job_id
    payload.revision_log.append(
        {
            "user": current_user.email,
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "action": "payload_update",
        }
    )
    payload = build_graph(payload.nodes, payload.spans, payload.equipment, payload)
    payload = validate_graph(payload)
    path = job_output_dir(job_id) / "technical_payload_reviewed.json"
    export_payload_json(payload, path)
    jobs.update(
        job_id,
        reviewed_payload_path=str(path),
        status=JobStatus.NEEDS_REVIEW.value,
        confidence=payload.confidence_global,
        message="Payload revisado salvo.",
    )
    return jsonify({"ok": True, "confidence": payload.confidence_global})


@bp.route("/jobs/<job_id>/approve", methods=["POST"])
@login_required
def approve(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    if not user_can_edit_job(job):
        abort(403)
    jobs.update(job_id, status=JobStatus.APPROVED.value, message="Extracao aprovada para geracao.")
    return jsonify({"ok": True})


@bp.route("/jobs/<job_id>/generate", methods=["POST"])
@login_required
def generate(job_id: str):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    if not user_can_generate_job(job):
        abort(403)
    path = Path(job.reviewed_payload_path or job.payload_path or "")
    if not path.exists():
        abort(404)
    jobs.update(job_id, status=JobStatus.GENERATING.value, message="Gerando saidas.")
    payload = load_payload_json(path)
    outputs = generate_outputs(payload, Path(job.original_pdf_path))
    report = load_validation_report(job_id)
    summary = output_summary(payload, report)
    output_status = str(summary.get("output_status") or "").lower()
    validation_status = str(summary.get("validation_status") or "").upper()
    status = JobStatus.DONE.value if output_status == "final_candidate" else JobStatus.NEEDS_REVIEW.value
    if validation_status == "BLOCKED" or output_status == "blocked":
        status = JobStatus.NEEDS_REVIEW.value
    message = (
        "Candidato final gerado pelo pipeline output-first."
        if output_status == "final_candidate"
        else "Rascunho gerado para revisao pelo pipeline output-first."
    )
    if validation_status == "BLOCKED" or output_status == "blocked":
        message = "Saida bloqueada. Revise erros antes de homologar."
    city_group = normalize_city_group(
        str(payload.meta.get("municipality") or ""),
        fallback=normalize_city_group(job.city_group, fallback="caxias_do_sul"),
    )
    jobs.update(
        job_id,
        status=status,
        message=message,
        reviewed_payload_path=str(outputs["json"]),
        croqui_pdf_path=str(outputs["pdf"]),
        croqui_png_path=str(outputs["png"]),
        excel_path=str(outputs["xls"]),
        confidence=payload.confidence_global,
        city_group=city_group,
    )
    return jsonify(
        {
            "ok": True,
            "outputs": {key: str(value) for key, value in outputs.items()},
            "summary": summary,
            "artifacts": _artifact_links(jobs.get(job_id)),
        }
    )


def _load_job_payload(job) -> TechnicalPayload:
    path = Path(job.reviewed_payload_path or job.payload_path or "")
    if path.exists():
        return load_payload_json(path)
    return TechnicalPayload(job_id=job.id)


def _build_and_store_graph(job_id: str, payload: TechnicalPayload, pdf_path: Path | None) -> CroquiGraph:
    payload.job_id = job_id
    payload = ensure_output_contract(payload, pdf_path, force_rebuild=True)
    export_payload_json(payload, job_output_dir(job_id) / "technical_payload.json")
    graph = croqui_graph_from_payload(payload)
    write_json(_graph_path(job_id), graph.as_dict())
    return graph


def _graph_path(job_id: str) -> Path:
    return job_output_dir(job_id) / "croqui_graph.json"


def _artifact_links(job) -> list[dict]:
    if job is None:
        return []
    links = []
    for item in artifact_summary(job):
        links.append(
            {
                **item,
                "download_url": url_for("api.download_artifact", job_id=job.id, kind=item["kind"]),
            }
        )
    return links


def _public_user(user) -> dict:
    return {
        "email": getattr(user, "email", ""),
        "name": getattr(user, "name", ""),
        "role": getattr(user, "role", ""),
        "city_group": getattr(user, "city_group", ""),
    }
