from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _path_from_env(name: str, default: str) -> Path:
    value = os.environ.get(name, default)
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    secret_key: str = os.environ.get("SECRET_KEY", "change-me")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///data/croqui_engine.db")
    upload_dir: Path = _path_from_env("UPLOAD_DIR", "data/uploads")
    output_dir: Path = _path_from_env("OUTPUT_DIR", "data/outputs")
    tmp_dir: Path = ROOT_DIR / "data" / "tmp"
    jobel_logo_path: Path = _path_from_env(
        "JOBEL_LOGO_PATH", "croqui_engine/app/static/img/jobel_logo.png"
    )
    admin_email: str = os.environ.get("CROQUI_ADMIN_EMAIL", "admin@jobel.local")
    admin_password: str = os.environ.get("CROQUI_ADMIN_PASSWORD", "Jobel@2026!")
    max_upload_mb: int = int(os.environ.get("MAX_UPLOAD_MB", "80"))
    excel_template_path: str = os.environ.get("CROQUI_EXCEL_TEMPLATE_PATH", "")
    golden_corpus_path: str = os.environ.get("CROQUI_GOLDEN_CORPUS_PATH", "CROQUI IA")
    engine_mode: str = os.environ.get("CROQUI_ENGINE_MODE", "v2")
    use_official_catalog: bool = os.environ.get("CROQUI_USE_OFFICIAL_CATALOG", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enable_benchmark: bool = os.environ.get("CROQUI_ENABLE_BENCHMARK", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    show_training_tools: bool = os.environ.get("CROQUI_SHOW_TRAINING_TOOLS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    use_corpus_reference_outputs: bool = os.environ.get(
        "CROQUI_USE_CORPUS_REFERENCE_OUTPUTS", "true"
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    engine_version: str = "0.1-local"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.replace("sqlite:///", "", 1)
            db_path = Path(raw)
            if not db_path.is_absolute():
                db_path = self.root_dir / db_path
            return f"sqlite:///{db_path}"
        return self.database_url


settings = Settings()


def ensure_data_dirs() -> None:
    for path in (settings.upload_dir, settings.output_dir, settings.tmp_dir):
        path.mkdir(parents=True, exist_ok=True)
    db_url = settings.sqlalchemy_url
    if db_url.startswith("sqlite:///"):
        Path(db_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
