from __future__ import annotations

from pathlib import Path

from croqui_engine.core.config import settings


def corpus_data_dir() -> Path:
    path = settings.data_dir / "corpus"
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path(default: str | Path | None = None) -> Path:
    raw = Path(default) if default else corpus_data_dir() / "registry.json"
    if not raw.is_absolute():
        raw = settings.root_dir / raw
    raw.parent.mkdir(parents=True, exist_ok=True)
    return raw


def ground_truth_dir(case_id: str) -> Path:
    path = corpus_data_dir() / "ground_truth" / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalogs_dir() -> Path:
    path = settings.data_dir / "catalogs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def benchmark_latest_dir() -> Path:
    path = settings.data_dir / "benchmark" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path
