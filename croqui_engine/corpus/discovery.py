from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.models import CorpusFile, CorpusRegistry, GoldenCase

IGNORED_NAMES = {".DS_Store", "desktop.ini", "Thumbs.db"}
PROJECT_TOKENS = ("PROJETO", "PROETO", "PROJ", " A1", " A2", " A3", " A4")
EQUIPMENT_RE = re.compile(r"\b(TR|FU|FC|RL|CF)\s*(\d{3,8})\b", re.IGNORECASE)


def resolve_corpus_path(path: str | Path | None = None, zip_path: str | Path | None = None) -> Path:
    if zip_path:
        return _extract_zip(Path(zip_path))
    raw = Path(path or settings.golden_corpus_path)
    if not raw.is_absolute():
        raw = settings.root_dir / raw
    if not raw.exists():
        raise FileNotFoundError(f"Corpus nao encontrado: {raw}")
    return raw


def discover_corpus(path: str | Path | None = None, zip_path: str | Path | None = None) -> CorpusRegistry:
    root = resolve_corpus_path(path, zip_path)
    cases: list[GoldenCase] = []
    warnings: list[str] = []
    for directory in sorted(item for item in root.iterdir() if item.is_dir() and not _is_ignored(item)):
        case = discover_case(directory)
        cases.append(case)
        warnings.extend(f"{case.case_id}: {warning}" for warning in case.warnings)

    registry = CorpusRegistry(source_path=str(root), cases=cases, warnings=warnings)
    registry.total_cases = len(cases)
    registry.complete_cases = sum(1 for case in cases if case.status == "COMPLETE")
    registry.missing_target_pdf = sum(1 for case in cases if case.status == "MISSING_TARGET_PDF")
    registry.missing_project = sum(1 for case in cases if case.status == "MISSING_PROJECT")
    registry.missing_xls = sum(1 for case in cases if case.status == "MISSING_XLS")
    registry.invalid_cases = sum(1 for case in cases if case.status == "INVALID")
    counts: dict[str, int] = {}
    for case in cases:
        key = case.equipment_type_from_name or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    registry.equipment_type_counts = dict(sorted(counts.items()))
    return registry


def discover_case(directory: Path) -> GoldenCase:
    project_pdfs: list[CorpusFile] = []
    target_pdfs: list[CorpusFile] = []
    xls_files: list[CorpusFile] = []
    other_files: list[CorpusFile] = []
    warnings: list[str] = []
    equipment_type = None
    equipment_code = None

    for path in sorted(item for item in directory.iterdir() if item.is_file() and not _is_ignored(item)):
        kind = classify_file(path)
        cfile = CorpusFile(
            path=str(path),
            name=path.name,
            kind=kind,
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
        )
        if kind == "PROJECT_PDF":
            project_pdfs.append(cfile)
        elif kind == "TARGET_CROQUI_PDF":
            target_pdfs.append(cfile)
            match = EQUIPMENT_RE.search(path.stem)
            if match and not equipment_code:
                equipment_type, equipment_code = match.group(1).upper(), match.group(2)
        elif kind == "TARGET_CROQUI_XLS":
            xls_files.append(cfile)
            match = EQUIPMENT_RE.search(path.stem)
            if match and not equipment_code:
                equipment_type, equipment_code = match.group(1).upper(), match.group(2)
        else:
            other_files.append(cfile)

    if len(xls_files) > 1:
        warnings.append("Mais de um XLS final encontrado; usando o primeiro por ordem alfabetica.")
    target_xls = xls_files[0] if xls_files else None
    status = _status(project_pdfs, target_pdfs, target_xls)
    if not target_pdfs:
        warnings.append("TARGET_PDF_MISSING")
    if not project_pdfs:
        warnings.append("PROJECT_PDF_MISSING")
    if target_xls is None:
        warnings.append("TARGET_XLS_MISSING")

    return GoldenCase(
        case_id=directory.name,
        directory=str(directory),
        project_pdfs=project_pdfs,
        target_croqui_pdfs=target_pdfs,
        target_croqui_xls=target_xls,
        other_files=other_files + xls_files[1:],
        equipment_type_from_name=equipment_type,
        equipment_code_from_name=equipment_code,
        status=status,
        warnings=warnings,
    )


def classify_file(path: Path) -> str:
    suffix = path.suffix.lower()
    upper = f" {path.stem.upper()} "
    if suffix == ".xls":
        return "TARGET_CROQUI_XLS"
    if suffix != ".pdf":
        return "OTHER"
    is_project = any(token in upper for token in PROJECT_TOKENS)
    if is_project:
        return "PROJECT_PDF"
    if "CROQUI" in upper:
        return "TARGET_CROQUI_PDF"
    return "OTHER"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _status(projects: list[CorpusFile], targets: list[CorpusFile], xls: CorpusFile | None) -> str:
    if not projects:
        return "MISSING_PROJECT"
    if xls is None:
        return "MISSING_XLS"
    if not targets:
        return "MISSING_TARGET_PDF"
    return "COMPLETE"


def _is_ignored(path: Path) -> bool:
    return path.name in IGNORED_NAMES or path.name.startswith("._") or path.name == "__MACOSX"


def _extract_zip(zip_path: Path) -> Path:
    if not zip_path.is_absolute():
        zip_path = settings.root_dir / zip_path
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP do corpus nao encontrado: {zip_path}")
    target = settings.root_dir / "data" / "golden_corpus" / zip_path.stem
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target)
    children = [child for child in target.iterdir() if child.is_dir() and not _is_ignored(child)]
    return children[0] if len(children) == 1 else target
