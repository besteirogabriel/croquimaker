from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from statistics import mean
from typing import Any

from croqui_engine.benchmark.visual_metrics import visual_metrics
from croqui_engine.core.pipeline import generate_outputs, process_pdf
from croqui_engine.corpus.discovery import discover_corpus
from croqui_engine.corpus.models import CorpusRegistry, GoldenCase
from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import benchmark_latest_dir
from croqui_engine.output.contract import output_contract_from_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark generico output-first do corpus.")
    parser.add_argument("--input", default="data/corpus", help="Diretorio do corpus ou data/corpus.")
    parser.add_argument("--mode", default="generic", choices=["generic"], help="Modo de avaliacao.")
    parser.add_argument("--case-id", default="", help="Executa apenas um caso.")
    parser.add_argument("--limit", type=int, default=0, help="Limite opcional de casos.")
    parser.add_argument(
        "--leave-one-out",
        action="store_true",
        help="Registra modo leave-one-out. A geracao generica nao usa target do caso.",
    )
    parser.add_argument(
        "--render-contact-sheet",
        action="store_true",
        help="Renderiza folha de contato target x gerado depois da geracao generica.",
    )
    args = parser.parse_args()

    summary = run_generic_corpus(
        Path(args.input),
        case_id=args.case_id or None,
        limit=args.limit or None,
        leave_one_out=args.leave_one_out,
        render_contact_sheet=args.render_contact_sheet,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def run_generic_corpus(
    input_path: Path,
    *,
    case_id: str | None = None,
    limit: int | None = None,
    leave_one_out: bool = False,
    render_contact_sheet: bool = False,
) -> dict[str, Any]:
    registry = _load_registry_for_input(input_path)
    cases = [case for case in registry.cases if case.status == "COMPLETE"]
    if case_id:
        cases = [case for case in cases if case.case_id == case_id]
    if limit is not None:
        cases = cases[:limit]

    output_dir = benchmark_latest_dir() / "generic"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_run_case(case, output_dir / "cases" / case.case_id) for case in cases]
    summary = _summary(results, leave_one_out=leave_one_out)
    if render_contact_sheet:
        contact_sheet = _write_contact_sheet(results, output_dir / "contact_sheet.png")
        if contact_sheet:
            summary["contact_sheet_path"] = str(contact_sheet)
    (output_dir / "generic_benchmark_summary.json").write_text(
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
        expected_code = case.equipment_code_from_name or ""
        expected_type = "FC" if case.equipment_type_from_name == "CF" else (case.equipment_type_from_name or "")
        expected_label = f"{expected_type} {expected_code}".strip()

        payload = process_pdf(project_pdf, f"generic_{case.case_id}")
        outputs = generate_outputs(payload, project_pdf)
        contract = output_contract_from_payload(payload)
        if not contract:
            raise ValueError("Contrato de output nao foi criado")
        visual = _visual_comparison_for_case(case, outputs["pdf"], output_dir)

        selected_label = contract.expected_or_selected_main_equipment or ""
        selected_code = contract.selected_equipment_code or ""
        header_equipment = contract.header.get("equipment", "")
        pdf_xls_consistency = 1.0
        main_ok = selected_code == expected_code if expected_code else False
        header_ok = _norm(header_equipment) == _norm(expected_label) if expected_label else False
        focus_ok = contract.primary_focus_code == expected_code if expected_code else False
        included_recall = 1.0 if expected_code and expected_code in contract.included_codes else 0.0
        excluded_precision = 1.0 if expected_code and expected_code not in contract.excluded_codes else 0.0
        incorrect_or_uncertain = (expected_code and selected_code != expected_code) or not contract.final_output_allowed
        low_confidence_correctly_flagged = 1.0 if incorrect_or_uncertain and not contract.final_output_allowed else 0.0

        warnings = list(contract.warnings)
        if visual.get("warning"):
            warnings.append(visual["warning"])

        result = {
            "case_id": case.case_id,
            "expected_main_equipment": expected_label,
            "selected_main_equipment": selected_label,
            "selected_equipment_confidence": contract.selected_equipment_confidence,
            "focus_confidence": contract.focus_confidence,
            "output_status": contract.output_status,
            "validation_status": contract.validation_status,
            "final_output_allowed": contract.final_output_allowed,
            "main_equipment_accuracy": 1.0 if main_ok else 0.0,
            "header_accuracy": 1.0 if header_ok else 0.0,
            "primary_focus_accuracy": 1.0 if focus_ok else 0.0,
            "included_codes_recall": included_recall,
            "excluded_remote_codes_precision": excluded_precision,
            "pdf_xls_consistency": pdf_xls_consistency,
            "visual_score": visual.get("visual_score"),
            "final_output_allowed_rate": 1.0 if contract.final_output_allowed else 0.0,
            "low_confidence_correctly_flagged_rate": low_confidence_correctly_flagged,
            "outputs": {key: str(value) for key, value in outputs.items()},
            "target_pdf": visual.get("target_pdf"),
            "visual": visual.get("metrics") or {},
            "blocking_errors": contract.blocking_errors,
            "warnings": warnings,
        }
        (output_dir / "generic_result.json").write_text(
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
            "header_accuracy": 0.0,
            "primary_focus_accuracy": 0.0,
            "included_codes_recall": 0.0,
            "excluded_remote_codes_precision": 0.0,
            "pdf_xls_consistency": 0.0,
            "visual_score": 0.0,
            "final_output_allowed_rate": 0.0,
            "low_confidence_correctly_flagged_rate": 0.0,
        }
        (output_dir / "generic_error.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result


def _summary(results: list[dict[str, Any]], *, leave_one_out: bool) -> dict[str, Any]:
    metric_names = [
        "main_equipment_accuracy",
        "header_accuracy",
        "primary_focus_accuracy",
        "included_codes_recall",
        "excluded_remote_codes_precision",
        "pdf_xls_consistency",
        "visual_score",
        "final_output_allowed_rate",
        "low_confidence_correctly_flagged_rate",
    ]
    return {
        "mode": "generic",
        "leave_one_out": leave_one_out,
        "cases": len(results),
        "comparable_cases": sum(1 for result in results if result.get("visual_score") is not None),
        "metrics": {
            name: _mean_metric(results, name)
            for name in metric_names
        },
        "results": results,
    }


def _visual_comparison_for_case(
    case: GoldenCase,
    generated_pdf: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if not case.target_croqui_pdfs:
        return {"warning": {"code": "TARGET_PDF_MISSING_FOR_VISUAL_COMPARE"}}
    target_pdf = Path(case.target_croqui_pdfs[0].path)
    try:
        metrics = visual_metrics(target_pdf, generated_pdf, output_dir)
    except Exception as exc:
        return {
            "target_pdf": str(target_pdf),
            "warning": {"code": "VISUAL_COMPARE_FAILED", "message": str(exc)},
        }
    return {
        "target_pdf": str(target_pdf),
        "visual_score": metrics.get("visual_score"),
        "metrics": metrics,
    }


def _write_contact_sheet(results: list[dict[str, Any]], output_path: Path) -> Path | None:
    comparable = [
        result
        for result in results
        if (result.get("visual") or {}).get("target_drawing_png")
        and (result.get("visual") or {}).get("generated_drawing_png")
    ]
    if not comparable:
        return None
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected = sorted(comparable, key=lambda item: float(item.get("visual_score") or 0.0))[:10]
    cell_w, image_h, header_h = 560, 330, 44
    sheet = Image.new("RGB", (cell_w * 2, header_h + image_h * len(selected)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("Arial.ttf", 18)
        small_font = ImageFont.truetype("Arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.text((12, 12), "Target", fill=(0, 0, 0), font=font)
    draw.text((cell_w + 12, 12), "Generated", fill=(0, 0, 0), font=font)
    for row, result in enumerate(selected):
        top = header_h + row * image_h
        visual = result.get("visual") or {}
        label = (
            f"{result.get('case_id')} | score={result.get('visual_score')} | "
            f"status={result.get('output_status')}"
        )
        draw.text((12, top + 6), label, fill=(0, 0, 0), font=small_font)
        draw.text((cell_w + 12, top + 6), label, fill=(0, 0, 0), font=small_font)
        for col, key in enumerate(("target_drawing_png", "generated_drawing_png")):
            image = Image.open(Path(visual[key])).convert("RGB")
            image = ImageOps.contain(image, (cell_w - 24, image_h - 42))
            x = col * cell_w + 12
            y = top + 34
            sheet.paste(image, (x, y))
            draw.rectangle((col * cell_w, top, (col + 1) * cell_w - 1, top + image_h - 1), outline=(210, 210, 210))
    sheet.save(output_path)
    return output_path


def _mean_metric(results: list[dict[str, Any]], name: str) -> float:
    values = [float(result[name]) for result in results if result.get(name) is not None]
    return round(mean(values), 4) if values else 0.0


def _load_registry_for_input(input_path: Path) -> CorpusRegistry:
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    if input_path.name == "corpus" and (input_path / "registry.json").exists():
        return load_registry(input_path / "registry.json")
    if (input_path / "ground_truth").exists() and (input_path / "registry.json").exists():
        return load_registry(input_path / "registry.json")
    return discover_corpus(input_path)


def _norm(value: str) -> str:
    return " ".join(str(value or "").upper().split())


if __name__ == "__main__":
    main()
