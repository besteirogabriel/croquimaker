from __future__ import annotations

import logging
from pathlib import Path


def configure_job_logger(job_id: str, output_dir: Path) -> logging.Logger:
    log_dir = output_dir / job_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"croqui_engine.job.{job_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_dir / "processamento.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger
