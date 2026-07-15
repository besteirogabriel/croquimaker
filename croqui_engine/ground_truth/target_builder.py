from __future__ import annotations

import json
from pathlib import Path

from croqui_engine.corpus.models import GoldenCase
from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import ground_truth_dir
from croqui_engine.ground_truth.models import TargetCroquiPayload
from croqui_engine.ground_truth.pdf_target_extractor import extract_target_pdf
from croqui_engine.ground_truth.serializer import save_target_payload
from croqui_engine.ground_truth.xls_target_extractor import extract_target_xls


def build_target_for_case(case: GoldenCase) -> TargetCroquiPayload:
    warnings = list(case.warnings)
    pdf_data = None
    xls_profile = None

    if case.target_croqui_pdfs:
        pdf_path = Path(case.target_croqui_pdfs[0].path)
        pdf_data = extract_target_pdf(case.case_id, pdf_path)
    else:
        warnings.append("TARGET_PDF_MISSING")

    if case.target_croqui_xls:
        xls_path = Path(case.target_croqui_xls.path)
        xls_profile = extract_target_xls(case.case_id, xls_path)
    else:
        warnings.append("TARGET_XLS_MISSING")

    payload = TargetCroquiPayload(
        case_id=case.case_id,
        page_size=pdf_data["page_size"] if pdf_data else (0.0, 0.0),
        header_fields=pdf_data["header_fields"] if pdf_data else {},
        viability_table=pdf_data["viability_table"] if pdf_data else {},
        texts=pdf_data["texts"] if pdf_data else [],
        symbols=pdf_data["symbols"] if pdf_data else [],
        lines=pdf_data["lines"] if pdf_data else [],
        areas=pdf_data["areas"] if pdf_data else [],
        xls_profile=xls_profile or {},
        extracted_from_pdf=pdf_data is not None,
        extracted_from_xls=xls_profile is not None,
        warnings=sorted(set(warnings)),
    )
    out_dir = ground_truth_dir(case.case_id)
    save_target_payload(payload, out_dir / "target_payload.json")
    if pdf_data:
        (out_dir / "target_pdf_objects.json").write_text(
            json.dumps(_jsonable_pdf_data(pdf_data), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if xls_profile:
        (out_dir / "target_xls_profile.json").write_text(
            json.dumps(xls_profile, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return payload


def build_targets(case_id: str | None = None, limit: int | None = None) -> list[TargetCroquiPayload]:
    registry = load_registry()
    cases = registry.cases
    if case_id:
        cases = [registry.case_map()[case_id]]
    if limit is not None:
        cases = cases[:limit]
    return [build_target_for_case(case) for case in cases]


def _jsonable_pdf_data(pdf_data: dict) -> dict:
    out = dict(pdf_data)
    for key in ("texts", "lines", "symbols", "areas"):
        out[key] = [item.as_dict() for item in out.get(key, [])]
    return out

