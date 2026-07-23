import copy
import re


REQUIRED_KEYS = ["meta", "nos", "trechos", "equipamentos", "areas", "textos"]
VIABILITY_ANSWERS = ("Sim", "Não", "Não Avaliado")
DEFAULT_VIABILITY = ("Sim",) * 9 + ("Não",)

STRING_FIELD = {"type": "string"}

PROJECT_SCHEMA = {
    "type": "object",
    "required": REQUIRED_KEYS,
    "additionalProperties": False,
    "properties": {
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "os": STRING_FIELD,
                "tipo": STRING_FIELD,
                "municipio": STRING_FIELD,
                "departamento": STRING_FIELD,
                "equipamento": STRING_FIELD,
                "data_levantamento": STRING_FIELD,
                "responsavel": STRING_FIELD,
                "obra": STRING_FIELD,
                "endereco": STRING_FIELD,
                "cliente": STRING_FIELD,
            },
            "required": ["os", "tipo", "municipio", "departamento", "equipamento", "data_levantamento", "responsavel", "obra", "endereco", "cliente"],
        },
        "nos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"id": STRING_FIELD, "tipo": STRING_FIELD, "x": STRING_FIELD, "y": STRING_FIELD, "label": STRING_FIELD, "observacao": STRING_FIELD},
                "required": ["id", "tipo", "x", "y", "label", "observacao"],
            },
        },
        "trechos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"de": STRING_FIELD, "para": STRING_FIELD, "tipo": STRING_FIELD, "cabo": STRING_FIELD, "comprimento": STRING_FIELD, "observacao": STRING_FIELD},
                "required": ["de", "para", "tipo", "cabo", "comprimento", "observacao"],
            },
        },
        "equipamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"tipo": STRING_FIELD, "codigo": STRING_FIELD, "no_id": STRING_FIELD, "estado": STRING_FIELD, "observacao": STRING_FIELD},
                "required": ["tipo", "codigo", "no_id", "estado", "observacao"],
            },
        },
        "areas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nome": STRING_FIELD,
                    "tipo": STRING_FIELD,
                    "nos": STRING_FIELD,
                    "observacao": STRING_FIELD,
                },
                "required": ["nome", "tipo", "nos", "observacao"],
            },
        },
        "textos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"texto": STRING_FIELD, "no_id": STRING_FIELD, "tipo": STRING_FIELD},
                "required": ["texto", "no_id", "tipo"],
            },
        },
    },
}


def sanitizar_projeto(obj: dict) -> dict:
    obj = copy.deepcopy(obj if isinstance(obj, dict) else {})
    for key in REQUIRED_KEYS:
        esperado_dict = key == "meta"
        val = obj.get(key)
        if esperado_dict:
            if not isinstance(val, dict):
                obj[key] = {}
        elif not isinstance(val, list):
            obj[key] = []

    obj["nos"] = _dedupe_by_id(_normalize_nodes(obj["nos"]))
    obj["trechos"] = _normalize_trechos(obj["trechos"])
    obj["equipamentos"] = _normalize_equipamentos(obj["equipamentos"])
    obj["areas"] = _normalize_areas(obj["areas"])
    obj["textos"] = _normalize_textos(obj["textos"])

    node_set = {n["id"] for n in obj["nos"]}
    for t in obj["trechos"]:
        for k in ("de", "para"):
            nid = str(t.get(k, ""))
            if nid and re.match(r"^P\d+$", nid) and nid not in node_set:
                obj["nos"].append({
                    "id": nid,
                    "tipo": "POSTE_EXISTENTE",
                    "x": "",
                    "y": "",
                    "label": nid,
                    "observacao": "Auto-criado",
                })
                node_set.add(nid)

    fallback = next((n["id"] for n in obj["nos"] if re.match(r"^P\d+$", n["id"])), "")
    for eq in obj["equipamentos"]:
        if not eq.get("no_id") or eq["no_id"] not in node_set:
            eq["no_id"] = fallback

    for area in obj["areas"]:
        area["nos"] = " ".join(
            node_id for node_id in _node_ids(area.get("nos", ""))
            if node_id in node_set
        )
    for text in obj["textos"]:
        if text.get("no_id") not in node_set:
            text["no_id"] = ""

    obj["trechos"] = [
        t for t in obj["trechos"]
        if t.get("de") and t.get("para")
        and t["de"] in node_set and t["para"] in node_set
        and t["de"] != t["para"]
    ]
    viability = obj.get("viabilidade")
    viability_rows = (
        viability.get("respostas")
        if isinstance(viability, dict)
        else None
    )
    obj["viabilidade"] = {
        "respostas": (
            normalizar_viabilidade(viability_rows)
            if viability_rows
            else viabilidade_automatica()
        )
    }
    return obj


def assert_schema(obj: dict) -> None:
    if not isinstance(obj, dict):
        raise ValueError("Resposta invalida")
    for key in REQUIRED_KEYS:
        if key not in obj:
            raise ValueError("Resposta incompleta")
    if not isinstance(obj["meta"], dict):
        raise ValueError("Resposta invalida")
    for key in REQUIRED_KEYS[1:]:
        if not isinstance(obj[key], list):
            raise ValueError("Resposta invalida")


def _extract_p(text: str) -> str:
    m = re.search(r"\bP\s*0*(\d+)\b", str(text), re.I)
    return f"P{int(m.group(1))}" if m else ""


def _normalize_nodes(rows: list) -> list:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("id") or row.get("label") or "")
        pid = _extract_p(raw)
        if not pid:
            continue
        row["id"] = pid
        row.setdefault("label", pid)
        row.setdefault("tipo", "POSTE_EXISTENTE")
        out.append(row)
    return out


def _normalize_trechos(rows: list) -> list:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        de = _extract_p(str(row.get("de", "")))
        para = _extract_p(str(row.get("para", "")))
        if not de or not para:
            texto = " ".join(str(v) for v in row.values())
            m = re.search(r"V\s*(\d+)\s*[-–]\s*(\d+)", texto, re.I)
            if m:
                de = f"P{int(m.group(1))}"
                para = f"P{int(m.group(2))}"
        if not de or not para:
            continue
        row["de"] = de
        row["para"] = para
        row.setdefault("tipo", "MT")
        out.append(row)
    return out


def _normalize_equipamentos(rows: list) -> list:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        p = _extract_p(str(row.get("no_id", "")))
        if p:
            row["no_id"] = p
        out.append(row)
    return out


def _node_ids(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            f"P{int(number)}"
            for number in re.findall(r"\bP\s*0*(\d+)\b", str(value), re.I)
        )
    )


def _normalize_areas(rows: list) -> list:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "nome": str(row.get("nome", "")).strip(),
            "tipo": str(row.get("tipo", "")).strip().upper(),
            "nos": " ".join(_node_ids(row.get("nos", ""))),
            "observacao": str(row.get("observacao", "")).strip(),
        })
    return out


def _normalize_textos(rows: list) -> list:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        node_ids = _node_ids(row.get("no_id", ""))
        out.append({
            "texto": str(row.get("texto", "")).strip(),
            "no_id": node_ids[0] if node_ids else "",
            "tipo": str(row.get("tipo", "")).strip().upper(),
        })
    return out


def _dedupe_by_id(rows: list) -> list:
    seen = set()
    out = []
    for row in rows:
        pid = str(row.get("id", "")).strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(row)
    return out


def normalizar_viabilidade(rows) -> list[str]:
    """Normalize the ten mandatory RGE viability answers.

    Missing or invalid answers become "Não Avaliado"; they must never turn
    into an implicit safety attestation.
    """

    aliases = {
        "sim": "Sim",
        "nao": "Não",
        "não": "Não",
        "nao avaliado": "Não Avaliado",
        "não avaliado": "Não Avaliado",
    }
    values = list(rows) if isinstance(rows, (list, tuple)) else []
    normalized = []
    for value in values[:10]:
        key = re.sub(r"\s+", " ", str(value).strip().lower())
        normalized.append(aliases.get(key, "Não Avaliado"))
    normalized.extend(["Não Avaliado"] * (10 - len(normalized)))
    return normalized


def viabilidade_automatica() -> list[str]:
    """Return the standard RGE viability profile used by generated croquis."""

    return list(DEFAULT_VIABILITY)
