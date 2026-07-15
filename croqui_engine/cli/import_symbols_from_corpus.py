from __future__ import annotations

import argparse

from croqui_engine.cli.import_corpus import main as import_corpus_main
from croqui_engine.symbols.official_catalog import build_official_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa simbologia oficial inicial dos XLS do corpus.")
    parser.add_argument("--path", default=None, help="Pasta do corpus; se informado, reimporta registry antes.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.path:
        import sys

        previous = sys.argv
        try:
            sys.argv = ["import_corpus", "--path", args.path]
            import_corpus_main()
        finally:
            sys.argv = previous
    catalog = build_official_catalog(limit=args.limit)
    print("Catalogo oficial inicial gerado")
    print(f"Casos fonte: {catalog['source_cases']}")
    print(f"Simbolos: {len(catalog['symbols'])}")
    print(f"Materiais: {len(catalog['materials'])}")
    print(f"Estilos de linha: {len(catalog['line_styles'])}")


if __name__ == "__main__":
    main()
