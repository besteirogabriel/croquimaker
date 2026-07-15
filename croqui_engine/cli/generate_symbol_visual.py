from __future__ import annotations

import argparse
from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.registry import load_registry
from croqui_engine.symbols.visual_catalog import generate_simbologia_svg_from_xls


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera SVG local da aba Simbologia para a UI.")
    parser.add_argument("--xls", default="", help="XLS aprovado usado apenas para extrair a prancha visual.")
    parser.add_argument(
        "--out",
        default=str(settings.root_dir / "croqui_engine/app/static/img/simbologia_oficial_extraida.svg"),
    )
    args = parser.parse_args()
    xls_path = Path(args.xls) if args.xls else _first_catalog_xls()
    output_path = generate_simbologia_svg_from_xls(xls_path, Path(args.out))
    print(output_path)


def _first_catalog_xls() -> Path:
    registry = load_registry()
    for case in registry.cases:
        if case.target_croqui_xls:
            return Path(case.target_croqui_xls.path)
    raise FileNotFoundError("Nenhum XLS com aba Simbologia encontrado no registry.")


if __name__ == "__main__":
    main()
