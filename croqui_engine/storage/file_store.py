from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from croqui_engine.core.config import settings


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def job_upload_dir(job_id: str) -> Path:
    path = settings.upload_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_output_dir(job_id: str) -> Path:
    path = settings.output_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_pdf(file: FileStorage, job_id: str) -> Path:
    filename = secure_filename(file.filename or "projeto.pdf")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Envie um arquivo PDF.")
    target = job_upload_dir(job_id) / "original.pdf"
    file.save(target)
    original_name = job_upload_dir(job_id) / "original_filename.txt"
    original_name.write_text(filename, encoding="utf-8")
    return target


def write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_name(value: str, fallback: str = "croqui") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_.")
    return cleaned or fallback


def copy_to_output(source: Path, job_id: str, name: str) -> Path:
    target = job_output_dir(job_id) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def zip_directory(source_dir: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        if source_dir.exists():
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(source_dir))
    return output_path
