from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from statistics import mean
from typing import Any

from croqui_engine.core.pipeline import process_pdf
from croqui_engine.corpus.discovery import discover_corpus
from croqui_engine.corpus.models import CorpusRegistry, GoldenCase
from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import benchmark_latest_dir
from croqui_engine.graph.croqui_graph import croqui_graph_from_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark do pipeline CroquiGraph output-first.")
    parser.add_argument("--input", default="data/corpus")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_graph_pipeline(
        Path(args.input),
        case_id=args.case_id or None,
        limit=args.limit or None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def run_graph_pipeline(
    input_path: Path,
    *,
    case_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    registry = _load_registry_for_input(input_path)
    cases = [case for case in registry.cases if case.status == "COMPLETE"]
    if case_id:
        cases = [case for case in cases if case.case_id == case_id]
    if limit is not None:
        cases = cases[:limit]
    output_dir = benchmark_latest_dir() / "graph_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_run_case(case, output_dir / "cases" / case.case_id) for case in cases]
    summary = _summary(results)
    (output_dir / "graph_pipeline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def _run_case(case: GoldenCase, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not case.project_pdfs:
            raise ValueError("Caso sem PDF bruto")
        project_pdf = Path(case.project_pdfs[0].path)
        payload = process_pdf(project_pdf, f"graph_{case.case_id}")
        graph = croqui_graph_from_payload(payload)
        graph_path = output_dir / "croqui_graph.json"
        graph_path.write_text(json.dumps(graph.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        expected_code = case.equipment_code_from_name or ""
        expected_type = "FC" if case.equipment_type_from_name == "CF" else (case.equipment_type_from_name or "")
        selected_label = f"{graph.mainEquipment.type} {graph.mainEquipment.code}".strip()
        expected_label = f"{expected_type} {expected_code}".strip()
        result = {
            "case_id": case.case_id,
            "graph_path": str(graph_path),
            "expected_main_equipment": expected_label,
            "selected_main_equipment": selected_label,
            "main_equipment_accuracy": 1.0 if expected_code and graph.mainEquipment.code == expected_code else 0.0,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "has_main_equipment": 1.0 if graph.mainEquipment.code else 0.0,
            "status": graph.validation.status,
            "warnings": graph.validation.warnings,
            "blocking_errors": graph.validation.blockingErrors,
        }
        (output_dir / "graph_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
    except Exception as exc:
        result = {
            "case_id": case.case_id,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "main_equipment_accuracy": 0.0,
            "node_count": 0,
            "edge_count": 0,
            "has_main_equipment": 0.0,
        }
        (output_dir / "graph_error.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "croqui_graph_pipeline",
        "cases": len(results),
        "errors": sum(1 for result in results if result.get("error")),
        "metrics": {
            "main_equipment_accuracy": _mean(results, "main_equipment_accuracy"),
            "has_main_equipment_rate": _mean(results, "has_main_equipment"),
            "avg_node_count": _mean(results, "node_count"),
            "avg_edge_count": _mean(results, "edge_count"),
        },
        "results": results,
    }


def _load_registry_for_input(input_path: Path) -> CorpusRegistry:
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    if input_path.name == "corpus" and (input_path / "registry.json").exists():
        return load_registry(input_path / "registry.json")
    if (input_path / "ground_truth").exists() and (input_path / "registry.json").exists():
        return load_registry(input_path / "registry.json")
    return discover_corpus(input_path)


def _mean(results: list[dict[str, Any]], key: str) -> float:
    values = [float(result[key]) for result in results if result.get(key) is not None]
    return round(mean(values), 4) if values else 0.0


if __name__ == "__main__":
    main()
