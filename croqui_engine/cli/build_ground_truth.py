from __future__ import annotations

import argparse

from croqui_engine.ground_truth.target_builder import build_targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera ground truth a partir do corpus aprovado.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", default=None, help="ID do caso.")
    group.add_argument("--all", action="store_true", help="Processa todos os casos do registry.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not args.case and not args.all:
        parser.error("Use --case <id> ou --all")
    targets = build_targets(case_id=args.case, limit=args.limit)
    print(f"Ground truth gerado: {len(targets)} caso(s)")
    for payload in targets:
        print(
            f"{payload.case_id}: pdf={payload.extracted_from_pdf} xls={payload.extracted_from_xls} "
            f"textos={len(payload.texts)} linhas={len(payload.lines)} avisos={len(payload.warnings)}"
        )


if __name__ == "__main__":
    main()
