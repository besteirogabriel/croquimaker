from __future__ import annotations

import json
import traceback
from pathlib import Path

from croqui_engine.benchmark.metrics import acceptance_level
from croqui_engine.benchmark.technical_metrics import compare_technical
from croqui_engine.benchmark.text_metrics import text_metrics
from croqui_engine.benchmark.visual_metrics import visual_metrics
from croqui_engine.core.models_v2 import GenerationComparison
from croqui_engine.core.pipeline import generate_outputs, process_pdf
from croqui_engine.corpus.models import GoldenCase
from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import benchmark_latest_dir
from croqui_engine.ground_truth.target_builder import build_target_for_case


def run_benchmark(
    case_id: str | None = None,
    limit: int | None = None,
    split: str | None = None,
    all_cases: bool = False,
) -> dict:
    registry = load_registry()
    cases = _select_cases(registry.cases, case_id=case_id, limit=limit, split=split, all_cases=all_cases)
    out_dir = benchmark_latest_dir()
    results = []
    for case in cases:
        result = run_case_benchmark(case, out_dir / "cases" / case.case_id)
        results.append(result)
    summary = _summary(results)
    summary_path = out_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_html_report(out_dir / "benchmark_report.html", summary, results)
    return summary


def run_case_benchmark(case: GoldenCase, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        target = build_target_for_case(case)
        if not case.project_pdfs:
            raise ValueError("Caso sem projeto bruto")
        if not case.target_croqui_pdfs:
            raise ValueError("Caso sem PDF final aprovado para benchmark visual")
        job_id = f"bench_{case.case_id}"
        payload = process_pdf(Path(case.project_pdfs[0].path), job_id)
        outputs = generate_outputs(payload, Path(case.project_pdfs[0].path))
        target_pdf = Path(case.target_croqui_pdfs[0].path)
        generated_pdf = outputs["pdf"]
        visual = visual_metrics(target_pdf, generated_pdf, output_dir)
        text = text_metrics(target_pdf, generated_pdf)
        technical = compare_technical(case, payload)
        level = acceptance_level(
            visual["visual_score"],
            text["text_score"],
            technical["equipment_score"],
            ok=True,
        )
        comparison = GenerationComparison(
            case_id=case.case_id,
            visual_score=visual["visual_score"],
            text_score=text["text_score"],
            geometry_score=visual["visual_score"],
            equipment_score=technical["equipment_score"],
            acceptance_level=level,
            generated_pdf_path=str(generated_pdf),
            target_pdf_path=str(target_pdf),
            visual_diff_path=visual["visual_diff_path"],
            blocking_differences=_blocking_differences(technical, visual, text),
            warnings=[{"code": warning} for warning in target.warnings],
            metrics={"visual": visual, "text": text, "technical": technical},
        )
        comparison_path = output_dir / "comparison.json"
        comparison_path.write_text(
            json.dumps(comparison.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return comparison.model_dump(mode="json")
    except Exception as exc:
        result = {
            "case_id": case.case_id,
            "acceptance_level": "BLOCKED",
            "visual_score": 0.0,
            "text_score": 0.0,
            "equipment_score": 0.0,
            "blocking_differences": [{"code": "BENCHMARK_EXCEPTION", "message": str(exc)}],
            "warnings": [],
            "metrics": {},
        }
        (output_dir / "error.txt").write_text(
            f"{exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
        return result


def _select_cases(
    cases: list[GoldenCase],
    case_id: str | None,
    limit: int | None,
    split: str | None,
    all_cases: bool,
) -> list[GoldenCase]:
    if case_id:
        return [case for case in cases if case.case_id == case_id]
    selected = [case for case in cases if case.status == "COMPLETE"]
    if split:
        selected = _stable_split(selected, split)
    if not all_cases and limit is None:
        limit = 3
    return selected[:limit] if limit is not None else selected


def _stable_split(cases: list[GoldenCase], split: str) -> list[GoldenCase]:
    ordered = sorted(cases, key=lambda case: case.case_id)
    n = len(ordered)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    parts = {
        "train": ordered[:train_end],
        "calibration": ordered[:train_end],
        "validation": ordered[train_end:val_end],
        "test": ordered[val_end:],
        "holdout": ordered[val_end:],
    }
    return parts.get(split, ordered)


def _blocking_differences(technical: dict, visual: dict, text: dict) -> list[dict]:
    out = []
    if technical.get("type_ok") is False:
        out.append({"code": "EQUIPMENT_TYPE_MISMATCH", "details": technical})
    if technical.get("code_ok") is False:
        out.append({"code": "EQUIPMENT_CODE_MISSING", "details": technical})
    if visual.get("visual_score", 0) < 0.65:
        out.append({"code": "LOW_VISUAL_SCORE", "score": visual.get("visual_score")})
    if text.get("text_score", 0) < 0.20:
        out.append({"code": "LOW_TEXT_SCORE", "score": text.get("text_score")})
    return out


def _summary(results: list[dict]) -> dict:
    if not results:
        return {"cases": 0, "average_visual_score": 0, "average_text_score": 0, "levels": {}}
    levels: dict[str, int] = {}
    for result in results:
        levels[result.get("acceptance_level", "BLOCKED")] = levels.get(result.get("acceptance_level", "BLOCKED"), 0) + 1
    return {
        "cases": len(results),
        "average_visual_score": round(sum(r.get("visual_score", 0) for r in results) / len(results), 4),
        "average_text_score": round(sum(r.get("text_score", 0) for r in results) / len(results), 4),
        "average_equipment_score": round(sum(r.get("equipment_score", 0) for r in results) / len(results), 4),
        "levels": levels,
        "results": results,
    }


def _write_html_report(path: Path, summary: dict, results: list[dict]) -> None:
    rows = "\n".join(
        f"<tr><td>{r['case_id']}</td><td>{r.get('acceptance_level')}</td>"
        f"<td>{r.get('visual_score', 0):.3f}</td><td>{r.get('text_score', 0):.3f}</td>"
        f"<td>{r.get('equipment_score', 0):.3f}</td></tr>"
        for r in results
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Benchmark JOBEL V2</title>
<style>body{{font-family:Arial,sans-serif;margin:28px;color:#172028}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d5dde3;padding:8px}}th{{background:#edf6fb}}</style>
</head><body>
<h1>Benchmark JOBEL V2</h1>
<p>Casos: {summary.get('cases')} | Visual medio: {summary.get('average_visual_score')} | Texto medio: {summary.get('average_text_score')}</p>
<table><thead><tr><th>Caso</th><th>Nivel</th><th>Visual</th><th>Texto</th><th>Equip.</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
    path.write_text(html, encoding="utf-8")

