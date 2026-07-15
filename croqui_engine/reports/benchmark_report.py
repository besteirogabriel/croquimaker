from __future__ import annotations

import json
from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.storage import benchmark_latest_dir
from croqui_engine.reports._pdf import build_simple_pdf


def generate_benchmark_report(output_path: Path | None = None) -> Path:
    summary_path = benchmark_latest_dir() / "benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    output_path = output_path or settings.root_dir / "docs" / "JOBEL_BENCHMARK_FIDELIDADE.pdf"
    results = summary.get("results", [])
    sections = [
        (
            "Resumo",
            [
                f"Casos: {summary.get('cases', 0)}",
                f"Visual medio: {summary.get('average_visual_score', 0)}",
                f"Texto medio: {summary.get('average_text_score', 0)}",
                f"Equipamento medio: {summary.get('average_equipment_score', 0)}",
                f"Niveis: {summary.get('levels', {})}",
            ],
        ),
        (
            "Casos",
            [
                f"{item.get('case_id')}: {item.get('acceptance_level')} visual={item.get('visual_score')} texto={item.get('text_score')} equip={item.get('equipment_score')}"
                for item in results[:80]
            ]
            or ["Benchmark ainda nao executado."],
        ),
        (
            "Observacao",
            [
                "Scores baixos nao devem ser mascarados; eles indicam divergencias reais contra o corpus aprovado.",
                "A engine V1 ainda e fallback. A V2 deve evoluir topologia/rendering usando estas metricas.",
            ],
        ),
    ]
    return build_simple_pdf("JOBEL - Benchmark de Fidelidade V2", sections, output_path)

