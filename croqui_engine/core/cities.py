from __future__ import annotations

import unicodedata

CITY_GROUP_LABELS = {
    "caxias_do_sul": "Caxias do Sul",
    "vacaria": "Vacaria",
    "admin": "Geral",
}

PUBLIC_CITY_GROUPS = ("caxias_do_sul", "vacaria")


def normalize_city_group(value: str | None, fallback: str = "caxias_do_sul") -> str:
    normalized = _plain(value or "")
    if "vacaria" in normalized:
        return "vacaria"
    if "caxias" in normalized:
        return "caxias_do_sul"
    if "admin" in normalized or "geral" in normalized:
        return "admin"
    return fallback if fallback in CITY_GROUP_LABELS else "caxias_do_sul"


def city_group_label(value: str | None) -> str:
    return CITY_GROUP_LABELS.get(normalize_city_group(value, fallback="admin"), "Caxias do Sul")


def _plain(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower().replace("-", " ").replace("_", " ")
