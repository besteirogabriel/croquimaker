from __future__ import annotations

from croqui_engine.reports.benchmark_report import generate_benchmark_report
from croqui_engine.reports.corpus_report import generate_corpus_report
from croqui_engine.reports.jobel_dependency_report_v2 import generate_dependency_report_v2
from croqui_engine.reports.symbol_catalog_report import generate_symbol_catalog_report


def main() -> None:
    paths = [
        generate_corpus_report(),
        generate_symbol_catalog_report(),
        generate_benchmark_report(),
        generate_dependency_report_v2(),
    ]
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
