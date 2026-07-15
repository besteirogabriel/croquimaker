from __future__ import annotations

import argparse
from pathlib import Path

from croqui_engine.symbols.official_symbol_assets import (
    default_symbol_assets_dir,
    generate_official_symbol_assets_from_xls,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera PNGs locais dos simbolos oficiais a partir da aba Simbologia."
    )
    parser.add_argument("--xls", required=True, help="XLS usado somente para preparar assets locais.")
    parser.add_argument("--out", default=str(default_symbol_assets_dir()))
    args = parser.parse_args()
    manifest = generate_official_symbol_assets_from_xls(Path(args.xls), Path(args.out))
    print(manifest)


if __name__ == "__main__":
    main()
