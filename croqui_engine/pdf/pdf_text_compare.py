from __future__ import annotations

import re
from pathlib import Path


def extract_pdf_text(pdf_path: Path) -> str:
    import fitz

    parts = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def compare_pdf_text(target_pdf: Path, generated_pdf: Path) -> dict:
    target_tokens = _tokens(extract_pdf_text(target_pdf))
    generated_tokens = _tokens(extract_pdf_text(generated_pdf))
    if not target_tokens and not generated_tokens:
        score = 1.0
    elif not target_tokens or not generated_tokens:
        score = 0.0
    else:
        score = len(target_tokens & generated_tokens) / len(target_tokens | generated_tokens)
    return {
        "text_score": round(score, 4),
        "target_token_count": len(target_tokens),
        "generated_token_count": len(generated_tokens),
        "missing_tokens_sample": sorted(target_tokens - generated_tokens)[:40],
        "extra_tokens_sample": sorted(generated_tokens - target_tokens)[:40],
    }


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-zÀ-ÿ0-9_/-]{2,}", value.upper())}

