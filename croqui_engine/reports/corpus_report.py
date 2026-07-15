from __future__ import annotations

from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.registry import load_registry
from croqui_engine.reports._pdf import build_simple_pdf


def generate_corpus_report(output_path: Path | None = None) -> Path:
    registry = load_registry()
    output_path = output_path or settings.root_dir / "docs" / "JOBEL_CORPUS_INVENTARIO.pdf"
    incomplete = [case for case in registry.cases if case.status != "COMPLETE"]
    sections = [
        (
            "Resumo",
            [
                f"Fonte: {registry.source_path}",
                f"Total de casos: {registry.total_cases}",
                f"Casos completos: {registry.complete_cases}",
                f"Sem PDF final: {registry.missing_target_pdf}",
                f"Sem projeto bruto: {registry.missing_project}",
                f"Sem XLS final: {registry.missing_xls}",
            ],
        ),
        (
            "Cobertura por Tipo de Equipamento",
            [f"{kind}: {count}" for kind, count in registry.equipment_type_counts.items()],
        ),
        (
            "Casos Incompletos e Anomalias",
            [f"{case.case_id}: {case.status} - {', '.join(case.warnings) or '-'}" for case in incomplete[:80]]
            or ["Nenhum caso incompleto registrado."],
        ),
        (
            "Recomendacao",
            [
                "Usar os casos completos para benchmark visual e tecnico.",
                "Usar casos sem PDF final apenas para benchmark Excel/estrutura documental.",
                "Manter split estavel de calibracao, validacao e holdout para evitar regressao.",
            ],
        ),
    ]
    return build_simple_pdf("JOBEL - Inventario do Corpus Aprovado", sections, output_path)

