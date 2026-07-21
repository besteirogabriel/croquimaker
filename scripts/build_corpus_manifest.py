import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "CROQUI IA"
OUT = ROOT / "data/corpus/manifest.json"
TEMPLATE_OUT = ROOT / "data/templates/croqui_template.xls"
TEMPLATE_NOTE = ROOT / "data/templates/README.md"


def kind(name: str) -> str:
    up = name.upper()
    if "PROJETO" in up or "PROETO" in up:
        return "projeto"
    if "CROQUI" in up:
        return "croqui"
    return "outro"


def equipment(name: str) -> str:
    up = name.upper()
    if re.search(r"\bTR\b", up):
        return "transformador"
    if re.search(r"\bFU\b", up):
        return "chave_fusivel"
    if re.search(r"\bRL\b", up):
        return "religador"
    if re.search(r"\bFC\b", up):
        return "chave_faca"
    return "indefinido"


def main():
    cases = []
    for folder in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        files = sorted(p for p in folder.iterdir() if p.is_file())
        projeto = next((p for p in files if kind(p.name) == "projeto" and p.suffix.lower() == ".pdf"), None)
        croqui_pdf = next((p for p in files if kind(p.name) == "croqui" and p.suffix.lower() == ".pdf"), None)
        croqui_xls = next((p for p in files if kind(p.name) == "croqui" and p.suffix.lower() in {".xls", ".xlsx"}), None)
        eq = equipment((croqui_pdf or croqui_xls or projeto or folder).name)
        cases.append({
            "id": folder.name,
            "equipamento": eq,
            "projeto_pdf": rel(projeto),
            "croqui_pdf": rel(croqui_pdf),
            "croqui_excel": rel(croqui_xls),
            "arquivos": [rel(p) for p in files],
        })

    selected = []
    used = set()
    for label, pred in [
        ("transformador", lambda c: c["equipamento"] == "transformador"),
        ("chave_fusivel", lambda c: c["equipamento"] == "chave_fusivel"),
        ("religador", lambda c: c["equipamento"] == "religador"),
        ("projeto_rural_longo", lambda c: c["projeto_pdf"] and ("A1" in c["projeto_pdf"].upper() or "2F" in c["projeto_pdf"].upper()) and c["equipamento"] == "chave_fusivel"),
        ("projeto_urbano_ramificacoes", lambda c: c["projeto_pdf"] and c["equipamento"] == "chave_faca"),
    ]:
        item = next((c for c in cases if c["id"] not in used and pred(c) and c["projeto_pdf"] and c["croqui_pdf"]), None)
        if item:
            selected.append({"perfil": label, "id": item["id"], "projeto_pdf": item["projeto_pdf"], "croqui_pdf": item["croqui_pdf"]})
            used.add(item["id"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"total": len(cases), "casos": cases, "regressao": selected}, ensure_ascii=False, indent=2), encoding="utf-8")

    template = next((c["croqui_excel"] for c in cases if c["croqui_excel"]), None)
    if template:
        src = ROOT / template
        TEMPLATE_OUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, TEMPLATE_OUT)
        TEMPLATE_NOTE.write_text(
            "Template Excel derivado de arquivo real do corpus.\n\n"
            f"Origem: `{template}`\n\n"
            "O arquivo original foi preservado sem alteracoes.\n",
            encoding="utf-8",
        )


def rel(path):
    return str(path.relative_to(ROOT)) if path else None


if __name__ == "__main__":
    main()
