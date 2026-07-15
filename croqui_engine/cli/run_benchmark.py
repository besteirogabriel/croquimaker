from __future__ import annotations

import argparse

from croqui_engine.benchmark.runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda benchmark V2 contra corpus aprovado.")
    parser.add_argument("--case", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    summary = run_benchmark(case_id=args.case, limit=args.limit, split=args.split, all_cases=args.all)
    print(f"Benchmark: {summary['cases']} caso(s)")
    print(f"Visual medio: {summary['average_visual_score']}")
    print(f"Texto medio: {summary['average_text_score']}")
    print(f"Equipamento medio: {summary['average_equipment_score']}")
    print(f"Niveis: {summary['levels']}")


if __name__ == "__main__":
    main()
