from __future__ import annotations

from pathlib import Path

from croqui_engine.corpus.storage import benchmark_latest_dir


def latest_benchmark_summary_path() -> Path:
    return benchmark_latest_dir() / "benchmark_summary.json"

