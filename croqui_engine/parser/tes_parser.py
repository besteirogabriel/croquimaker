from __future__ import annotations

import re
from datetime import UTC, datetime

from croqui_engine.core.models import Equipment


def parse_tes_text(text: str) -> dict:
    normalized = _normalize(text)
    meta: dict[str, str] = {}

    number = _first(
        normalized,
        [
            r"\bTES\s*(\d{5,})\b",
            r"\bNumero:\s*(\d{5,})\b",
            r"\bNúmero:\s*(\d{5,})\b",
        ],
    )
    if number:
        meta["tes_number"] = number

    fields = {
        "municipality": [r"Munic[ií]pio:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Estado:|Respons|Classifica|$)"],
        "state": [r"Estado:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Munic|$)"],
        "responsible": [r"Respons[aá]vel:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Classifica|Data|$)"],
        "service_classification": [r"Classifica[cç][aã]o(?: do Servi[cç]o)?:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Data|$)"],
        "start_datetime": [r"In[ií]cio:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|T[eé]rmino|Fim|$)"],
        "end_datetime": [r"(?:T[eé]rmino|Fim):\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Descri|$)"],
        "address": [r"Endere[cç]o:\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Executor|Prestador|$)"],
        "executor": [r"(?:Executor|Prestador):\s*([^\n\r]+?)(?:\n|\r|\s{2,}|Equipe|$)"],
    }
    for key, patterns in fields.items():
        value = _first(normalized, patterns)
        if value:
            meta[key] = value.strip(" :-")

    description = _section(
        normalized,
        ["Descricao do Servico", "Descrição do Serviço", "Area de trabalho", "Área de trabalho"],
        ["Condicoes para a Execucao", "Condições para a Execução", "Plano de Manobra"],
    )
    if description:
        meta["service_description"] = description

    conditions = _section(
        normalized,
        ["Condicoes para a Execucao", "Condições para a Execução"],
        ["Plano de Manobra", "Passos de Manobra", "Equipes"],
    )
    if conditions:
        meta["execution_conditions"] = conditions

    plan = _section(normalized, ["Plano de Manobra", "Plano de Manobras"], ["Passos"])
    if plan:
        meta["switching_plan"] = plan

    steps = _section(normalized, ["Passos de Manobra", "Passos de Manobras"], ["Equipes", "Observ"])
    if steps:
        meta["switching_steps"] = steps

    actions = parse_tes_actions(normalized)
    if actions:
        meta["tes_actions"] = actions
        main = next((a for a in actions if a["status"] in {"abrir", "fechar"}), actions[0])
        meta["main_switching_equipment"] = f"{main['label']} {main['code']}".strip()

    if "processed_at" not in meta:
        meta["processed_at"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    return meta


def parse_tes_equipment(text: str) -> list[Equipment]:
    equipment: list[Equipment] = []
    seen: set[tuple[str, str, str]] = set()
    for action in parse_tes_actions(text):
        key = (action["code"], action["type"], action["status"])
        if key in seen:
            continue
        seen.add(key)
        equipment.append(
            Equipment(
                code=action["code"],
                type=action["type"],
                confidence=0.85 if action["status"] in {"abrir", "retirar", "instalar"} else 0.7,
                raw_text=action["raw_text"],
                status=action["status"],
            )
        )
    return equipment


def parse_tes_actions(text: str) -> list[dict]:
    normalized = _normalize(text)
    patterns = [
        (r"\bAbrir\s+FC\s+(\d{5,8})", "FC", "CHAVE_COMANDO", "abrir"),
        (r"\bFechar\s+FC\s+(\d{5,8})", "FC", "CHAVE_COMANDO", "fechar"),
        (r"\bAbrir\s+FU(?:\s+TR)?\s+(\d{5,8})", "FU", "CHAVE_FUSIVEL", "abrir"),
        (r"\bFechar\s+FU(?:\s+TR)?\s+(\d{5,8})", "FU", "CHAVE_FUSIVEL", "fechar"),
        (r"\bFaca\s+LB\s+(\d{5,8})", "FC", "CHAVE_COMANDO", "referencia"),
        (r"\bretirar\s+FU\s+(\d{5,8})", "FU", "CHAVE_FUSIVEL", "retirar"),
        (r"\binstalar\s+TRs?\s+(.+?)\s+novos?", "TR", "TRANSFORMADOR", "instalar"),
    ]
    actions: list[dict] = []
    for pattern, label, eq_type, status in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE | re.DOTALL):
            raw = match.group(0)
            if label == "TR":
                for code in re.findall(r"\b\d{5,8}\b", match.group(1)):
                    actions.append(
                        {
                            "label": label,
                            "code": code,
                            "type": eq_type,
                            "status": status,
                            "raw_text": raw,
                        }
                    )
            else:
                actions.append(
                    {
                        "label": label,
                        "code": match.group(1),
                        "type": eq_type,
                        "status": status,
                        "raw_text": raw,
                    }
                )
    return actions


def _normalize(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text or "").replace("\r", "\n")


def _first(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _section(text: str, starts: list[str], ends: list[str]) -> str:
    stripped = _strip_accents(text)
    for start in starts:
        start_clean = _strip_accents(start)
        idx = stripped.lower().find(start_clean.lower())
        if idx < 0:
            continue
        end_idx = len(text)
        for end in ends:
            candidate = stripped.lower().find(_strip_accents(end).lower(), idx + len(start))
            if candidate > idx:
                end_idx = min(end_idx, candidate)
        section = text[idx:end_idx]
        return re.sub(r"\s+", " ", section).strip(" :-")[:2000]
    return ""


def _strip_accents(value: str) -> str:
    table = str.maketrans(
        "ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç",
        "AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuc",
    )
    return value.translate(table)
