from __future__ import annotations

import argparse
import shutil

from croqui_engine.core.config import ensure_data_dirs, settings
from croqui_engine.storage.database import Job, SessionLocal, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara ambiente MVP JOBEL.")
    parser.add_argument("--reset-jobs", action="store_true", help="Remove jobs, uploads e saidas antigos.")
    args = parser.parse_args()

    init_db()
    if args.reset_jobs:
        _reset_jobs()

    print("Ambiente MVP preparado.")
    print("Admin: admin@jobel.local / Jobel@2026!")
    print("Caxias: caxias1@jobel.local / Caxias@2026")
    print("Caxias: caxias2@jobel.local / Caxias@2026")
    print("Vacaria: vacaria1@jobel.local / Vacaria@2026")
    print("Vacaria: vacaria2@jobel.local / Vacaria@2026")


def _reset_jobs() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()
    for path in (settings.upload_dir, settings.output_dir):
        if path.exists():
            shutil.rmtree(path)
    ensure_data_dirs()


if __name__ == "__main__":
    main()
