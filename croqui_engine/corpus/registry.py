from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from croqui_engine.corpus.models import CorpusRegistry
from croqui_engine.corpus.storage import corpus_data_dir, registry_path
from croqui_engine.storage.database import engine


def save_registry(registry: CorpusRegistry, output: str | Path | None = None) -> Path:
    path = registry_path(output)
    path.write_text(json.dumps(registry.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    save_registry_sqlite(registry)
    write_import_report(registry)
    return path


def load_registry(path: str | Path | None = None) -> CorpusRegistry:
    raw = registry_path(path)
    return CorpusRegistry.model_validate_json(raw.read_text(encoding="utf-8"))


def save_registry_sqlite(registry: CorpusRegistry) -> Path:
    db_path = Path(str(engine.url).replace("sqlite:///", "", 1))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS golden_cases (
                case_id TEXT PRIMARY KEY,
                directory TEXT NOT NULL,
                status TEXT NOT NULL,
                equipment_type TEXT,
                equipment_code TEXT,
                project_count INTEGER NOT NULL,
                target_pdf_count INTEGER NOT NULL,
                has_xls INTEGER NOT NULL,
                warnings TEXT NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM golden_cases")
        for case in registry.cases:
            conn.execute(
                """
                INSERT INTO golden_cases (
                    case_id, directory, status, equipment_type, equipment_code,
                    project_count, target_pdf_count, has_xls, warnings
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case.case_id,
                    case.directory,
                    case.status,
                    case.equipment_type_from_name,
                    case.equipment_code_from_name,
                    len(case.project_pdfs),
                    len(case.target_croqui_pdfs),
                    1 if case.target_croqui_xls else 0,
                    "\n".join(case.warnings),
                ),
            )
    return db_path


def write_import_report(registry: CorpusRegistry) -> Path:
    path = corpus_data_dir() / "import_report.md"
    lines = [
        "# Importacao do Corpus Aprovado",
        "",
        f"Fonte: `{registry.source_path}`",
        f"Total de casos: {registry.total_cases}",
        f"Completos: {registry.complete_cases}",
        f"Sem PDF final: {registry.missing_target_pdf}",
        f"Sem projeto: {registry.missing_project}",
        f"Sem XLS: {registry.missing_xls}",
        f"Invalidos: {registry.invalid_cases}",
        "",
        "## Tipos por nome",
        "",
    ]
    for key, count in registry.equipment_type_counts.items():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Warnings", ""])
    for warning in registry.warnings[:500]:
        lines.append(f"- {warning}")
    if len(registry.warnings) > 500:
        lines.append(f"- ... mais {len(registry.warnings) - 500} warnings")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
