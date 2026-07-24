from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import mimetypes
import os
import queue
import re
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from .auth import AuthPaths, AuthStore, PROJECTS, load_or_create_session_secret
from .core.pipeline import gerar
from .project_store import ProjectStore, ProjectStorePaths, utc_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOG = logging.getLogger(__name__)

MAX_UPLOAD = int(os.getenv("CROQUIMAKER_MAX_UPLOAD_MB", "80")) * 1024 * 1024
DATA_DIR = Path(os.getenv("CROQUIMAKER_DATA_DIR", "generated"))
PROJECTS_DIR = Path(os.getenv("CROQUIMAKER_PROJECTS_DIR", str(DATA_DIR / "projects")))
DISPLAY_TIMEZONE = ZoneInfo(os.getenv("CROQUIMAKER_TIMEZONE", "America/Sao_Paulo"))
PUBLIC_MESSAGES = {
    "queued": "Recebendo projeto",
    "reading": "Lendo projeto",
    "building": "Construindo croqui",
    "finishing": "Finalizando",
    "done": "Croqui concluído",
    "error": "Não foi possível processar este projeto",
}
STATE_LABELS = {
    "queued": "Na fila",
    "reading": "Em leitura",
    "building": "Em geração",
    "finishing": "Finalizando",
    "done": "Concluído",
    "error": "Falhou",
}
AUDIT_ACTION_LABELS = {
    "auth.login": "Acesso à plataforma",
    "auth.login_failed": "Tentativa de acesso",
    "auth.logout": "Saída da plataforma",
    "project.scope_changed": "Troca de unidade ativa",
    "project.created": "Projeto criado",
    "project.processing_started": "Processamento iniciado",
    "project.completed": "Croqui concluído",
    "project.failed": "Processamento falhou",
    "artifact.downloaded": "Arquivo baixado",
    "audit.exported": "Auditoria exportada",
    "project.imported": "Projeto anterior indexado",
}
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

app = Flask(__name__)
auth_paths = AuthPaths.from_environment()
auth_store = AuthStore(auth_paths.database, auth_paths.initial_credentials)
auth_store.initialize()
project_store = ProjectStore(ProjectStorePaths.from_environment().database)
project_store.initialize()
app.config.update(
    MAX_CONTENT_LENGTH=MAX_UPLOAD,
    SECRET_KEY=load_or_create_session_secret(auth_paths.session_secret),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("CROQUIMAKER_COOKIE_SECURE", "0") == "1",
)
jobs: dict[str, dict] = {}
work_q: queue.Queue[str] = queue.Queue()


def _project_jobs_dir(project_slug: str) -> Path:
    if project_slug not in PROJECTS:
        raise ValueError("Projeto invalido")
    return PROJECTS_DIR / project_slug / "jobs"


def _job_key(project_slug: str, job_id: str) -> str:
    return f"{project_slug}:{job_id}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _artifact_names(project_slug: str, job_id: str, created_at: str) -> tuple[str, str, str]:
    stamp = _parse_timestamp(created_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = job_id[:10].upper()
    base = f"{project_slug.upper()}-{stamp}-{suffix}"
    return (
        f"PROJETO-{base}.pdf",
        f"CROQUI-{base}.pdf",
        f"CROQUI-{base}.xls",
    )


def _safe_original_filename(value: str) -> str:
    filename = value.replace("\\", "/").split("/")[-1].strip()
    filename = "".join(character for character in filename if ord(character) >= 32)
    return (filename or "projeto.pdf")[:180]


def _safe_stored_filename(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    normalized = value.replace("\\", "/").split("/")[-1]
    return normalized if normalized and normalized == value else fallback


def _hydrate_job(job: dict) -> dict:
    job_dir = _project_jobs_dir(job["project_slug"]) / job["id"]
    job["input_filename"] = _safe_stored_filename(
        job.get("input_filename"),
        "projeto.pdf",
    )
    job["output_pdf_filename"] = _safe_stored_filename(
        job.get("output_pdf_filename"),
        f"CROQUI-{job['project_slug'].upper()}-{job['id'][:8].upper()}.pdf",
    )
    job["output_xls_filename"] = _safe_stored_filename(
        job.get("output_xls_filename"),
        f"CROQUI-{job['project_slug'].upper()}-{job['id'][:8].upper()}.xls",
    )
    job["dir"] = str(job_dir)
    job["input"] = str(job_dir / job.get("input_filename", "projeto.pdf"))
    return job


def _job_manifest(job: dict) -> dict:
    return {
        "id": job["id"],
        "project_slug": job["project_slug"],
        "created_by_id": job.get("created_by_id"),
        "created_by": job.get("created_by", "legacy"),
        "original_filename": job.get("original_filename", "projeto.pdf"),
        "input_filename": job.get("input_filename", "projeto.pdf"),
        "output_pdf_filename": job.get("output_pdf_filename"),
        "output_xls_filename": job.get("output_xls_filename"),
        "state": job["state"],
        "message": job["message"],
        "has_excel": bool(job.get("has_excel")),
        "result": job.get("result", {}),
        "input_sha256": job.get("input_sha256"),
        "output_sha256": job.get("output_sha256"),
        "engine": job.get("engine"),
        "cached": bool(job.get("cached")),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error_summary": job.get("error_summary"),
    }


def _save_job(job: dict, *, touch: bool = True) -> None:
    if touch:
        job["updated_at"] = utc_now()
    job_dir = Path(job["dir"])
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "status.json"
    temporary_path = job_dir / "status.json.tmp"
    temporary_path.write_text(
        json.dumps(_job_manifest(job), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)
    project_store.save_job(job)


def _legacy_job(job_id: str, project_slug: str, job_dir: Path, manifest: dict) -> dict:
    source_path = job_dir / _safe_stored_filename(
        manifest.get("input_filename"),
        "projeto.pdf",
    )
    if not source_path.exists():
        source_path = job_dir / "projeto.pdf"
    created_at = manifest.get("created_at")
    if not created_at:
        source = source_path if source_path.exists() else job_dir
        created_at = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(
            timespec="seconds"
        )
    input_name, output_pdf_name, output_xls_name = _artifact_names(
        project_slug,
        job_id,
        created_at,
    )
    if source_path.exists() and source_path.name == "projeto.pdf":
        migrated_source = job_dir / input_name
        if not migrated_source.exists():
            os.replace(source_path, migrated_source)
        source_path = migrated_source
    else:
        input_name = source_path.name

    configured_pdf = _safe_stored_filename(
        manifest.get("output_pdf_filename"),
        "",
    )
    generic_pdf = job_dir / "croqui.pdf"
    if configured_pdf:
        output_pdf_name = configured_pdf
    elif generic_pdf.exists():
        os.replace(generic_pdf, job_dir / output_pdf_name)

    configured_xls = _safe_stored_filename(
        manifest.get("output_xls_filename"),
        "",
    )
    generic_xls = job_dir / "croqui.xls"
    if configured_xls:
        output_xls_name = configured_xls
    elif generic_xls.exists():
        os.replace(generic_xls, job_dir / output_xls_name)

    output_pdf_path = job_dir / output_pdf_name
    output_xls_path = job_dir / output_xls_name
    state = manifest.get("state")
    if state not in PUBLIC_MESSAGES:
        state = "done" if output_pdf_path.exists() else "error"
    job = {
        "id": job_id,
        "dir": str(job_dir),
        "project_slug": project_slug,
        "created_by_id": manifest.get("created_by_id"),
        "created_by": manifest.get("created_by", "legacy"),
        "original_filename": manifest.get("original_filename", source_path.name),
        "input_filename": input_name,
        "input": str(source_path),
        "output_pdf_filename": output_pdf_name,
        "output_xls_filename": output_xls_name,
        "state": state,
        "message": manifest.get("message", PUBLIC_MESSAGES[state]),
        "has_excel": output_xls_path.exists(),
        "result": manifest.get("result", {}),
        "input_sha256": manifest.get("input_sha256"),
        "output_sha256": manifest.get("output_sha256"),
        "engine": manifest.get("engine"),
        "cached": bool(manifest.get("cached")),
        "created_at": created_at,
        "updated_at": manifest.get("updated_at", created_at),
        "started_at": manifest.get("started_at"),
        "completed_at": manifest.get("completed_at"),
        "error_summary": manifest.get("error_summary"),
    }
    if source_path.exists() and not job["input_sha256"]:
        job["input_sha256"] = _sha256_file(source_path)
    if output_pdf_path.exists() and not job["output_sha256"]:
        job["output_sha256"] = _sha256_file(output_pdf_path)
    return job


def _load_job(job_id: str, project_slug: str) -> dict | None:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        return None
    key = _job_key(project_slug, job_id)
    if key in jobs:
        return jobs[key]
    stored = project_store.get_job(job_id, project_slug)
    if stored is not None:
        job = _hydrate_job(stored)
        jobs[key] = job
        return job

    job_dir = _project_jobs_dir(project_slug) / job_id
    status_path = job_dir / "status.json"
    if not status_path.exists():
        return None
    try:
        manifest = json.loads(status_path.read_text(encoding="utf-8"))
        if manifest.get("project_slug") != project_slug:
            return None
        job = _legacy_job(job_id, project_slug, job_dir, manifest)
        jobs[key] = job
        _save_job(job, touch=False)
        return job
    except Exception:
        LOG.exception("Nao foi possivel carregar status do projeto %s", job_id)
        return None


def _audit(
    action: str,
    *,
    outcome: str = "success",
    project_slug: str | None = None,
    job_id: str | None = None,
    details: dict | None = None,
    user: dict | None = None,
    actor_username: str | None = None,
) -> None:
    actor = user if user is not None else getattr(g, "user", None)
    try:
        project_store.record_event(
            actor_user_id=actor.get("id") if actor else None,
            actor_username=actor_username or (actor.get("username") if actor else "system"),
            action=action,
            outcome=outcome,
            project_slug=project_slug,
            job_id=job_id,
            source_address=request.remote_addr if request else None,
            details=details,
        )
    except Exception:
        LOG.exception("Nao foi possivel registrar evento de auditoria %s", action)


def _finalize_artifacts(job: dict) -> None:
    job_dir = Path(job["dir"])
    generic_pdf = job_dir / "croqui.pdf"
    output_pdf = job_dir / job["output_pdf_filename"]
    if generic_pdf.exists():
        os.replace(generic_pdf, output_pdf)
    if not output_pdf.exists():
        raise FileNotFoundError("Saida PDF nao foi gerada")

    generic_xls = job_dir / "croqui.xls"
    output_xls = job_dir / job["output_xls_filename"]
    if generic_xls.exists():
        os.replace(generic_xls, output_xls)
    job["has_excel"] = output_xls.exists()
    job["output_sha256"] = _sha256_file(output_pdf)


def _worker() -> None:
    while True:
        key = work_q.get()
        job = jobs.get(key)
        if job is None:
            work_q.task_done()
            continue
        try:
            def progresso(message: str) -> None:
                job["state"] = (
                    "reading"
                    if message == PUBLIC_MESSAGES["reading"]
                    else "building"
                    if message == PUBLIC_MESSAGES["building"]
                    else "finishing"
                )
                job["message"] = message
                _save_job(job)

            job["state"] = "reading"
            job["message"] = PUBLIC_MESSAGES["reading"]
            job["started_at"] = job.get("started_at") or utc_now()
            job["error_summary"] = None
            _save_job(job)
            project_store.record_event(
                actor_user_id=job.get("created_by_id"),
                actor_username=job["created_by"],
                action="project.processing_started",
                project_slug=job["project_slug"],
                job_id=job["id"],
                details={"original_filename": job["original_filename"]},
            )
            result = gerar(
                Path(job["input"]),
                Path(job["dir"]),
                progresso=progresso,
            )
            _finalize_artifacts(job)
            job["result"] = result
            job["input_sha256"] = result.get("sha256") or job.get("input_sha256")
            job["engine"] = result.get("engine")
            job["cached"] = bool(result.get("cached"))
            job["state"] = "done"
            job["message"] = PUBLIC_MESSAGES["done"]
            job["completed_at"] = utc_now()
            _save_job(job)
            project_store.record_event(
                actor_user_id=job.get("created_by_id"),
                actor_username=job["created_by"],
                action="project.completed",
                project_slug=job["project_slug"],
                job_id=job["id"],
                details={
                    "output_filename": job["output_pdf_filename"],
                    "output_sha256": job["output_sha256"],
                },
            )
        except Exception as exc:
            LOG.exception("Erro completo no projeto %s", key)
            job["state"] = "error"
            job["message"] = PUBLIC_MESSAGES["error"]
            job["completed_at"] = utc_now()
            job["error_summary"] = type(exc).__name__
            _save_job(job)
            project_store.record_event(
                actor_user_id=job.get("created_by_id"),
                actor_username=job["created_by"],
                action="project.failed",
                outcome="failure",
                project_slug=job["project_slug"],
                job_id=job["id"],
                details={"error_type": type(exc).__name__},
            )
        finally:
            work_q.task_done()


def _restore_saved_projects() -> None:
    for project_slug in PROJECTS:
        jobs_dir = _project_jobs_dir(project_slug)
        if not jobs_dir.exists():
            continue
        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir() or not JOB_ID_PATTERN.fullmatch(job_dir.name):
                continue
            status_path = job_dir / "status.json"
            if project_store.get_job(job_dir.name, project_slug) is not None:
                continue
            try:
                manifest = (
                    json.loads(status_path.read_text(encoding="utf-8"))
                    if status_path.exists()
                    else {}
                )
                job = _legacy_job(job_dir.name, project_slug, job_dir, manifest)
                _save_job(job, touch=False)
                project_store.record_event(
                    actor_username="system",
                    action="project.imported",
                    project_slug=project_slug,
                    job_id=job["id"],
                    details={"original_filename": job["original_filename"]},
                    occurred_at=job["created_at"],
                )
            except Exception:
                LOG.exception("Nao foi possivel indexar projeto anterior %s", job_dir)

    for stored in project_store.pending_jobs():
        job = _hydrate_job(stored)
        if not Path(job["input"]).exists():
            job["state"] = "error"
            job["message"] = PUBLIC_MESSAGES["error"]
            job["completed_at"] = utc_now()
            job["error_summary"] = "MissingInput"
            _save_job(job)
            continue
        key = _job_key(job["project_slug"], job["id"])
        jobs[key] = job
        work_q.put(key)


_restore_saved_projects()
threading.Thread(target=_worker, daemon=True).start()


@app.before_request
def _load_authenticated_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = auth_store.get_user(int(user_id))
        if g.user is None:
            session.clear()
        elif g.user["role"] == "project":
            session["active_project"] = g.user["project_slug"]
        elif session.get("active_project") not in PROJECTS:
            session["active_project"] = "caxias"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify({"message": "Autenticacao necessaria"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def _csrf_token() -> str:
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def _valid_csrf() -> bool:
    supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("_csrf_token", "")
    return bool(expected and secrets.compare_digest(supplied, expected))


def csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _valid_csrf():
            if request.path.startswith("/api/"):
                return jsonify({"message": "Solicitacao invalida"}), 400
            abort(400)
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def _template_context() -> dict:
    return {
        "csrf_token": _csrf_token,
        "projects": PROJECTS,
        "state_labels": STATE_LABELS,
    }


@app.template_filter("date_br")
def _date_br(value: str | None) -> str:
    if not value:
        return "—"
    return _parse_timestamp(value).astimezone(DISPLAY_TIMEZONE).strftime("%d/%m/%Y %H:%M")


@app.template_filter("short_id")
def _short_id(value: str | None) -> str:
    return value[:8].upper() if value else "—"


@app.template_filter("short_hash")
def _short_hash(value: str | None) -> str:
    return value[:12].upper() if value else "—"


def _active_project_slug() -> str:
    if g.user["role"] == "project":
        return g.user["project_slug"]
    project_slug = session.get("active_project", "caxias")
    return project_slug if project_slug in PROJECTS else "caxias"


def _visible_project_slugs() -> tuple[str, ...]:
    if g.user["role"] == "admin":
        return tuple(PROJECTS)
    return (g.user["project_slug"],)


def _can_access_project(project_slug: str) -> bool:
    return project_slug in _visible_project_slugs()


def _shell_context(page: str) -> dict:
    active_project = _active_project_slug()
    return {
        "active_project": active_project,
        "active_project_name": PROJECTS[active_project],
        "user": g.user,
        "page": page,
    }


def _decorate_events(events: list[dict]) -> list[dict]:
    for event in events:
        event["action_label"] = AUDIT_ACTION_LABELS.get(event["action"], event["action"])
        event["project_name"] = (
            PROJECTS.get(event.get("project_slug"), "Sistema")
            if event.get("project_slug")
            else "Sistema"
        )
    return events


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        if not _valid_csrf():
            abort(400)
        supplied_username = request.form.get("username", "").strip()
        user = auth_store.authenticate(
            supplied_username,
            request.form.get("password", ""),
        )
        if user is None:
            error = "Usuario ou senha invalidos"
            _audit(
                "auth.login_failed",
                outcome="failure",
                actor_username=(supplied_username or "desconhecido")[:64],
            )
        else:
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["active_project"] = user["project_slug"] or "caxias"
            _csrf_token()
            _audit(
                "auth.login",
                project_slug=user["project_slug"],
                user=user,
            )
            return redirect(url_for("dashboard"))
    return render_template("login.html", error=error)


@app.post("/logout")
@login_required
@csrf_required
def logout():
    _audit(
        "auth.logout",
        project_slug=g.user.get("project_slug") or _active_project_slug(),
    )
    session.clear()
    return redirect(url_for("login"))


@app.post("/projeto-ativo")
@login_required
@csrf_required
def selecionar_projeto():
    if g.user["role"] != "admin":
        abort(403)
    project_slug = request.form.get("project_slug", "")
    if project_slug not in PROJECTS:
        abort(400)
    previous_slug = _active_project_slug()
    session["active_project"] = project_slug
    _audit(
        "project.scope_changed",
        project_slug=project_slug,
        details={"from": previous_slug, "to": project_slug},
    )
    destination = request.form.get("next", "")
    if not destination.startswith("/") or destination.startswith("//"):
        destination = url_for("dashboard")
    return redirect(destination)


@app.get("/")
@login_required
def dashboard():
    visible_slugs = _visible_project_slugs()
    recent_jobs = project_store.list_jobs(visible_slugs, limit=12)
    recent_events = _decorate_events(
        project_store.list_events(
            visible_slugs,
            limit=8,
            include_system=g.user["role"] == "admin",
        )
    )
    return render_template(
        "dashboard.html",
        stats=project_store.dashboard_stats(visible_slugs),
        recent_jobs=recent_jobs,
        recent_events=recent_events,
        audit_integrity=project_store.verify_audit_chain(),
        **_shell_context("dashboard"),
    )


@app.get("/novo")
@login_required
def novo_projeto():
    return render_template("index.html", **_shell_context("new"))


@app.get("/auditoria")
@login_required
def auditoria():
    visible_slugs = _visible_project_slugs()
    events = _decorate_events(
        project_store.list_events(
            visible_slugs,
            limit=250,
            include_system=g.user["role"] == "admin",
        )
    )
    return render_template(
        "audit.html",
        events=events,
        audit_integrity=project_store.verify_audit_chain(),
        **_shell_context("audit"),
    )


@app.get("/auditoria.csv")
@login_required
def exportar_auditoria():
    visible_slugs = _visible_project_slugs()
    events = project_store.list_events(
        visible_slugs,
        limit=1000,
        include_system=g.user["role"] == "admin",
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "data_hora_utc",
            "unidade",
            "usuario",
            "acao",
            "resultado",
            "projeto_id",
            "hash_evento",
        ]
    )
    for event in reversed(events):
        writer.writerow(
            [
                event["occurred_at"],
                event.get("project_slug") or "sistema",
                event["actor_username"],
                event["action"],
                event["outcome"],
                event.get("job_id") or "",
                event["event_hash"],
            ]
        )
    _audit(
        "audit.exported",
        project_slug=None if g.user["role"] == "admin" else g.user["project_slug"],
        details={"event_count": len(events)},
    )
    stamp = datetime.now(DISPLAY_TIMEZONE).strftime("%Y%m%d-%H%M%S")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="AUDITORIA-JOBEL-{stamp}.csv"'
        },
    )


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "audit_integrity": project_store.verify_audit_chain(),
        }
    )


@app.post("/api/projetos")
@login_required
@csrf_required
def criar_projeto():
    uploaded = request.files.get("arquivo")
    if not uploaded or not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    mime = uploaded.mimetype or mimetypes.guess_type(uploaded.filename)[0] or ""
    if mime not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400

    project_slug = _active_project_slug()
    job_id = uuid.uuid4().hex
    created_at = utc_now()
    input_filename, output_pdf_filename, output_xls_filename = _artifact_names(
        project_slug,
        job_id,
        created_at,
    )
    job_dir = _project_jobs_dir(project_slug) / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    input_path = job_dir / input_filename
    uploaded.save(input_path)
    with input_path.open("rb") as saved_input:
        signature = saved_input.read(4)
    if input_path.stat().st_size < 5 or signature != b"%PDF":
        input_path.unlink(missing_ok=True)
        job_dir.rmdir()
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400

    key = _job_key(project_slug, job_id)
    job = {
        "id": job_id,
        "dir": str(job_dir),
        "project_slug": project_slug,
        "created_by_id": g.user["id"],
        "created_by": g.user["username"],
        "original_filename": _safe_original_filename(uploaded.filename),
        "input_filename": input_filename,
        "input": str(input_path),
        "output_pdf_filename": output_pdf_filename,
        "output_xls_filename": output_xls_filename,
        "state": "queued",
        "message": PUBLIC_MESSAGES["queued"],
        "has_excel": False,
        "result": {},
        "input_sha256": _sha256_file(input_path),
        "output_sha256": None,
        "engine": None,
        "cached": False,
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "completed_at": None,
        "error_summary": None,
    }
    jobs[key] = job
    _save_job(job, touch=False)
    _audit(
        "project.created",
        project_slug=project_slug,
        job_id=job_id,
        details={
            "original_filename": job["original_filename"],
            "input_sha256": job["input_sha256"],
            "output_filename": output_pdf_filename,
        },
    )
    work_q.put(key)
    return jsonify(
        {
            "job_id": job_id,
            "project": project_slug,
            "state": "queued",
            "message": PUBLIC_MESSAGES["queued"],
            "output_filename": output_pdf_filename,
        }
    ), 202


@app.get("/api/projetos/<job_id>")
@login_required
def status(job_id):
    job = _load_job(job_id, _active_project_slug())
    if not job:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 404
    return jsonify(
        {
            "job_id": job_id,
            "state": job["state"],
            "message": job["message"],
            "has_excel": bool(job.get("has_excel")),
            "output_filename": job.get("output_pdf_filename"),
        }
    )


def _result_path(job_id: str, project_slug: str, kind: str) -> tuple[Path, dict]:
    job = _load_job(job_id, project_slug)
    if not job or job.get("state") != "done":
        abort(404)
    name = (
        job.get("output_pdf_filename")
        if kind == "pdf"
        else job.get("output_xls_filename")
    )
    if not name:
        abort(404)
    job_dir = Path(job["dir"]).resolve()
    path = (job_dir / name).resolve()
    if path.parent != job_dir:
        abort(404)
    if not path.exists():
        abort(404)
    return path, job


def _send_artifact(project_slug: str, job_id: str, kind: str):
    if not _can_access_project(project_slug):
        abort(404)
    path, job = _result_path(job_id, project_slug, kind)
    _audit(
        "artifact.downloaded",
        project_slug=project_slug,
        job_id=job_id,
        details={
            "artifact": kind,
            "filename": path.name,
            "sha256": job.get("output_sha256") if kind == "pdf" else None,
        },
    )
    return send_file(path, as_attachment=True, download_name=path.name)


@app.get("/api/projetos/<job_id>/croqui.pdf")
@login_required
def baixar_pdf(job_id):
    return _send_artifact(_active_project_slug(), job_id, "pdf")


@app.get("/api/projetos/<job_id>/croqui.xls")
@login_required
def baixar_xls(job_id):
    return _send_artifact(_active_project_slug(), job_id, "xls")


@app.get("/api/unidades/<project_slug>/projetos/<job_id>/arquivo/<kind>")
@login_required
def baixar_arquivo_projeto(project_slug: str, job_id: str, kind: str):
    if project_slug not in PROJECTS or kind not in {"pdf", "xls"}:
        abort(404)
    return _send_artifact(project_slug, job_id, kind)
