from __future__ import annotations

import argparse

from croqui_engine.corpus.discovery import discover_corpus
from croqui_engine.corpus.registry import save_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa corpus aprovado JOBEL/RGE/CPFL.")
    parser.add_argument("--path", default=None, help="Pasta local do corpus aprovado.")
    parser.add_argument("--zip", dest="zip_path", default=None, help="ZIP do corpus.")
    parser.add_argument("--output", default=None, help="Arquivo registry.json de saida.")
    args = parser.parse_args()

    registry = discover_corpus(args.path, args.zip_path)
    output = save_registry(registry, args.output)
    print(f"Registry: {output}")
    print(f"Casos: {registry.total_cases}")
    print(f"Completos: {registry.complete_cases}")
    print(f"Sem PDF final: {registry.missing_target_pdf}")
    print(f"Sem projeto: {registry.missing_project}")
    print(f"Sem XLS: {registry.missing_xls}")
    print(f"Tipos: {registry.equipment_type_counts}")


if __name__ == "__main__":
    main()
