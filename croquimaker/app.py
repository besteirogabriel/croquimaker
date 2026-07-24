import json
import logging
import mimetypes
import os
import queue
import re
import secrets
import threading
import uuid
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOG = logging.getLogger(__name__)

MAX_UPLOAD = int(os.getenv("CROQUIMAKER_MAX_UPLOAD_MB", "80")) * 1024 * 1024
DATA_DIR = Path(os.getenv("CROQUIMAKER_DATA_DIR", "generated"))
PROJECTS_DIR = Path(os.getenv("CROQUIMAKER_PROJECTS_DIR", str(DATA_DIR / "projects")))
PUBLIC_MESSAGES = {
    "queued": "Recebendo projeto",
    "reading": "Lendo projeto",
    "building": "Construindo croqui",
    "finishing": "Finalizando",
    "done": "Croqui concluído",
    "error": "Não foi possível processar este projeto",
}
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

app = Flask(__name__)
auth_paths = AuthPaths.from_environment()
auth_store = AuthStore(auth_paths.database, auth_paths.initial_credentials)
auth_store.initialize()
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


def _job_public(job: dict) -> dict:
    return {
        "id": job["id"],
        "dir": job["dir"],
        "project_slug": job["project_slug"],
        "created_by": job["created_by"],
        "input": job.get("input", ""),
        "state": job["state"],
        "message": job["message"],
        "has_excel": bool(job.get("has_excel")),
        "result": job.get("result", {}),
    }


def _save_job(job: dict) -> None:
    path = Path(job["dir"]) / "status.json"
    path.write_text(json.dumps(_job_public(job), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_job(job_id: str, project_slug: str) -> dict | None:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        return None
    key = _job_key(project_slug, job_id)
    if key in jobs:
        return jobs[key]
    job_dir = _project_jobs_dir(project_slug) / job_id
    path = job_dir / "status.json"
    if not path.exists():
        if (job_dir / "croqui.pdf").exists():
            job = {
                "id": job_id,
                "dir": str(job_dir),
                "project_slug": project_slug,
                "created_by": "legacy",
                "input": str(job_dir / "projeto.pdf"),
                "state": "done",
                "message": PUBLIC_MESSAGES["done"],
                "has_excel": (job_dir / "croqui.xls").exists(),
            }
            jobs[key] = job
            _save_job(job)
            return job
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        if job.get("project_slug") != project_slug:
            return None
        job["dir"] = str(job_dir)
        job["input"] = str(job_dir / "projeto.pdf")
        jobs[key] = job
        return job
    except Exception:
        LOG.exception("Nao foi possivel carregar status do job %s", job_id)
        return None


def _worker():
    while True:
        key = work_q.get()
        job = jobs[key]
        try:
            def progresso(msg):
                job["state"] = "reading" if msg == "Lendo projeto" else "building" if msg == "Construindo croqui" else "finishing"
                job["message"] = msg
                _save_job(job)

            job["state"] = "reading"
            job["message"] = PUBLIC_MESSAGES["reading"]
            _save_job(job)
            result = gerar(
                Path(job["input"]),
                Path(job["dir"]),
                progresso=progresso,
            )
            job["result"] = result
            job["has_excel"] = (Path(job["dir"]) / "croqui.xls").exists()
            job["state"] = "done"
            job["message"] = PUBLIC_MESSAGES["done"]
            _save_job(job)
        except Exception:
            LOG.exception("Erro completo no job %s", key)
            job["state"] = "error"
            job["message"] = PUBLIC_MESSAGES["error"]
            _save_job(job)
        finally:
            work_q.task_done()


threading.Thread(target=_worker, daemon=True).start()


@app.before_request
def _load_authenticated_user():
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
def _template_context():
    return {"csrf_token": _csrf_token}


def _active_project_slug() -> str:
    if g.user["role"] == "project":
        return g.user["project_slug"]
    project_slug = session.get("active_project", "caxias")
    return project_slug if project_slug in PROJECTS else "caxias"


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        if not _valid_csrf():
            abort(400)
        user = auth_store.authenticate(
            request.form.get("username", ""),
            request.form.get("password", ""),
        )
        if user is None:
            error = "Usuario ou senha invalidos"
        else:
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["active_project"] = user["project_slug"] or "caxias"
            _csrf_token()
            return redirect(url_for("index"))
    return render_template("login.html", error=error)


@app.post("/logout")
@login_required
@csrf_required
def logout():
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
    session["active_project"] = project_slug
    return redirect(url_for("index"))


@app.get("/")
@login_required
def index():
    active_project = _active_project_slug()
    return render_template(
        "index.html",
        active_project=active_project,
        active_project_name=PROJECTS[active_project],
        projects=PROJECTS,
        user=g.user,
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/projetos")
@login_required
@csrf_required
def criar_projeto():
    f = request.files.get("arquivo")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    mime = f.mimetype or mimetypes.guess_type(f.filename)[0] or ""
    if mime not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    project_slug = _active_project_slug()
    job_id = uuid.uuid4().hex
    job_dir = _project_jobs_dir(project_slug) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "projeto.pdf"
    f.save(input_path)
    if input_path.stat().st_size < 5 or input_path.read_bytes()[:4] != b"%PDF":
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    key = _job_key(project_slug, job_id)
    jobs[key] = {
        "id": job_id,
        "dir": str(job_dir),
        "project_slug": project_slug,
        "created_by": g.user["username"],
        "input": str(input_path),
        "state": "queued",
        "message": PUBLIC_MESSAGES["queued"],
        "has_excel": False,
    }
    _save_job(jobs[key])
    work_q.put(key)
    return jsonify(
        {
            "job_id": job_id,
            "project": project_slug,
            "state": "queued",
            "message": PUBLIC_MESSAGES["queued"],
        }
    ), 202


@app.get("/api/projetos/<job_id>")
@login_required
def status(job_id):
    job = _load_job(job_id, _active_project_slug())
    if not job:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 404
    return jsonify({
        "job_id": job_id,
        "state": job["state"],
        "message": job["message"],
        "has_excel": bool(job.get("has_excel")),
    })


@app.get("/api/projetos/<job_id>/croqui.pdf")
@login_required
def baixar_pdf(job_id):
    path = _result_path(job_id, _active_project_slug(), "croqui.pdf")
    return send_file(path, as_attachment=True, download_name="croqui.pdf")


@app.get("/api/projetos/<job_id>/croqui.xls")
@login_required
def baixar_xls(job_id):
    path = _result_path(job_id, _active_project_slug(), "croqui.xls")
    return send_file(path, as_attachment=True, download_name="croqui.xls")


def _result_path(job_id: str, project_slug: str, name: str):
    job = _load_job(job_id, project_slug)
    if not job or job.get("state") != "done":
        abort(404)
    path = Path(job["dir"]) / name
    if not path.exists():
        abort(404)
    return path.resolve()
