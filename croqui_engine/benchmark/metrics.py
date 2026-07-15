from __future__ import annotations


def acceptance_level(visual_score: float, text_score: float, equipment_score: float, ok: bool) -> str:
    if not ok or equipment_score < 0.5:
        return "BLOCKED"
    combined = visual_score * 0.55 + text_score * 0.25 + equipment_score * 0.20
    if combined >= 0.92:
        return "APPROVED"
    if combined >= 0.85:
        return "HIGH"
    if combined >= 0.65:
        return "MEDIUM"
    return "LOW"

