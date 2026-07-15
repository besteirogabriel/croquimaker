from __future__ import annotations

from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.registry import load_registry
from croqui_engine.reports._pdf import build_simple_pdf
from croqui_engine.symbols.official_catalog import load_official_catalog


def generate_dependency_report_v2(output_path: Path | None = None) -> Path:
    registry = load_registry()
    catalog = load_official_catalog() or {}
    output_path = output_path or settings.root_dir / "docs" / "JOBEL_DEPENDENCIAS_RESTANTES_V2.pdf"
    sections = [
        (
            "O Que Ja Existe no Corpus",
            [
                f"{registry.total_cases} casos aprovados registrados.",
                f"{registry.complete_cases} casos com projeto, PDF final e XLS final.",
                f"{registry.missing_target_pdf} casos sem PDF final, aproveitaveis para Excel.",
                f"Catalogo inicial importado com {len(catalog.get('symbols', []))} simbolos consolidados.",
            ],
        ),
        (
            "Dependencias Restantes",
            [
                "Validacao oficial dos simbolos extraidos da aba Simbologia.",
                "Mapeamento celula a celula do XLS oficial por familia TR/FU/FC/RL.",
                "Definicao de criterio minimo de score visual/textual para homologacao.",
                "Confirmacao das regras de linha, cor, tracejado, camada e estado da rede.",
                "Definicao de workflow de aprovacao e assinatura tecnica.",
            ],
        ),
        (
            "Decisoes Que Travam Homologacao",
            [
                "Se o PDF final deve derivar do Excel ou do renderer proprio.",
                "Se o sistema pode usar OCR local em PDFs escaneados.",
                "Qual e o limite aceitavel para divergencia visual por regiao.",
                "Quais casos compoem calibracao, validacao e holdout oficial.",
            ],
        ),
    ]
    return build_simple_pdf("JOBEL - Dependencias Restantes V2", sections, output_path)

