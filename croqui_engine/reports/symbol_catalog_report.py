from __future__ import annotations

from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.reports._pdf import build_simple_pdf
from croqui_engine.symbols.official_catalog import load_official_catalog


def generate_symbol_catalog_report(output_path: Path | None = None) -> Path:
    catalog = load_official_catalog() or {}
    output_path = output_path or settings.root_dir / "docs" / "JOBEL_SIMBOLOGIA_IMPORTADA.pdf"
    symbols = catalog.get("symbols", [])
    materials = catalog.get("materials", [])
    sections = [
        (
            "Resumo",
            [
                f"Versao: {catalog.get('catalog_version', '-')}",
                f"Casos fonte: {catalog.get('source_cases', 0)}",
                f"Simbolos consolidados: {len(symbols)}",
                f"Materiais encontrados: {len(materials)}",
                f"Estilos de linha coletados: {len(catalog.get('line_styles', []))}",
            ],
        ),
        (
            "Simbolos",
            [
                f"{item.get('id')}: nomes={', '.join(item.get('names', [])[:8])}; origens={len(item.get('source_sheets', []))}"
                for item in symbols
            ]
            or ["Catalogo oficial ainda nao importado."],
        ),
        (
            "Lacunas",
            [
                "A leitura de objetos/desenhos internos do XLS legado ainda e limitada por bibliotecas Python.",
                "Os simbolos foram inferidos principalmente de textos/celulas da aba Simbologia.",
                "A JOBEL deve validar os itens consolidados antes de homologacao.",
            ],
        ),
    ]
    return build_simple_pdf("JOBEL - Simbologia Importada do Corpus", sections, output_path)

