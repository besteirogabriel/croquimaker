import logging
import mimetypes
import os
import queue
import threading
import uuid
import json
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from .core.pipeline import gerar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOG = logging.getLogger(__name__)

MAX_UPLOAD = int(os.getenv("CROQUIMAKER_MAX_UPLOAD_MB", "80")) * 1024 * 1024
JOBS_DIR = Path("generated/jobs")
PUBLIC_MESSAGES = {
    "queued": "Recebendo projeto",
    "reading": "Lendo projeto",
    "building": "Construindo croqui",
    "finishing": "Finalizando",
    "done": "Croqui concluído",
    "error": "Não foi possível processar este projeto",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
jobs: dict[str, dict] = {}
work_q: queue.Queue[str] = queue.Queue()


def _job_public(job: dict) -> dict:
    return {
        "id": job["id"],
        "dir": job["dir"],
        "input": job.get("input", ""),
        "state": job["state"],
        "message": job["message"],
        "has_excel": bool(job.get("has_excel")),
        "result": job.get("result", {}),
    }


def _save_job(job: dict) -> None:
    path = Path(job["dir"]) / "status.json"
    path.write_text(json.dumps(_job_public(job), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_job(job_id: str) -> dict | None:
    if job_id in jobs:
        return jobs[job_id]
    path = JOBS_DIR / job_id / "status.json"
    if not path.exists():
        job_dir = JOBS_DIR / job_id
        if (job_dir / "croqui.pdf").exists():
            job = {
                "id": job_id,
                "dir": str(job_dir),
                "input": str(job_dir / "projeto.pdf"),
                "state": "done",
                "message": PUBLIC_MESSAGES["done"],
                "has_excel": (job_dir / "croqui.xls").exists(),
            }
            jobs[job_id] = job
            _save_job(job)
            return job
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        jobs[job_id] = job
        return job
    except Exception:
        LOG.exception("Nao foi possivel carregar status do job %s", job_id)
        return None


def _worker():
    while True:
        job_id = work_q.get()
        job = jobs[job_id]
        try:
            def progresso(msg):
                job["state"] = "reading" if msg == "Lendo projeto" else "building" if msg == "Construindo croqui" else "finishing"
                job["message"] = msg
                _save_job(job)

            job["state"] = "reading"
            job["message"] = PUBLIC_MESSAGES["reading"]
            _save_job(job)
            result = gerar(Path(job["input"]), Path(job["dir"]), progresso=progresso)
            job["result"] = result
            job["has_excel"] = (Path(job["dir"]) / "croqui.xls").exists()
            job["state"] = "done"
            job["message"] = PUBLIC_MESSAGES["done"]
            _save_job(job)
        except Exception:
            LOG.exception("Erro completo no job %s", job_id)
            job["state"] = "error"
            job["message"] = PUBLIC_MESSAGES["error"]
            _save_job(job)
        finally:
            work_q.task_done()


threading.Thread(target=_worker, daemon=True).start()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/projetos")
def criar_projeto():
    f = request.files.get("arquivo")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    mime = f.mimetype or mimetypes.guess_type(f.filename)[0] or ""
    if mime not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "projeto.pdf"
    f.save(input_path)
    if input_path.stat().st_size < 5 or input_path.read_bytes()[:4] != b"%PDF":
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 400
    jobs[job_id] = {
        "id": job_id,
        "dir": str(job_dir),
        "input": str(input_path),
        "state": "queued",
        "message": PUBLIC_MESSAGES["queued"],
        "has_excel": False,
    }
    _save_job(jobs[job_id])
    work_q.put(job_id)
    return jsonify({"job_id": job_id, "state": "queued", "message": PUBLIC_MESSAGES["queued"]}), 202


@app.get("/api/projetos/<job_id>")
def status(job_id):
    job = _load_job(job_id)
    if not job:
        return jsonify({"message": PUBLIC_MESSAGES["error"]}), 404
    return jsonify({
        "job_id": job_id,
        "state": job["state"],
        "message": job["message"],
        "has_excel": bool(job.get("has_excel")),
    })


@app.get("/api/projetos/<job_id>/croqui.pdf")
def baixar_pdf(job_id):
    path = _result_path(job_id, "croqui.pdf")
    return send_file(path, as_attachment=True, download_name="croqui.pdf")


@app.get("/api/projetos/<job_id>/croqui.xls")
def baixar_xls(job_id):
    path = _result_path(job_id, "croqui.xls")
    return send_file(path, as_attachment=True, download_name="croqui.xls")


def _result_path(job_id: str, name: str):
    job = _load_job(job_id)
    if not job or job.get("state") != "done":
        abort(404)
    path = Path(job["dir"]) / name
    if not path.exists():
        abort(404)
    return path.resolve()
