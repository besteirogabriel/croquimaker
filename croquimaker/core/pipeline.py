import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

from .interpretador_ia import interpretar_pdf
from .schema import (
    assert_schema,
    normalizar_viabilidade,
    sanitizar_projeto,
    viabilidade_automatica,
)
from sistema.extractors import base
from sistema.generation.clean_projeto import render_clean_projeto
from sistema.generation.croqui_geometrico import render_croqui_geometrico

LOG = logging.getLogger(__name__)
CACHE_DIR = Path("generated/cache")
ENGINE_VERSION = "geometry-cad-v6-automatic-viability"
JOB_ARTIFACTS = (
    "croqui.pdf",
    "clean_projeto.pdf",
    "clean_projeto.png",
    "color_inventory.json",
    "extraction.json",
    "network_selection.json",
    "projeto.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gerar(
    caminho_pdf: Path,
    job_dir: Path,
    progresso=None,
    *,
    viabilidade: list[str] | None = None,
) -> dict:
    tempos = {}
    start = time.perf_counter()
    digest = sha256_file(caminho_pdf)
    viability_answers = (
        normalizar_viabilidade(viabilidade)
        if viabilidade is not None
        else viabilidade_automatica()
    )
    options_digest = hashlib.sha256(
        json.dumps(viability_answers, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    cache_dir = CACHE_DIR / f"{ENGINE_VERSION}-{digest}-{options_digest}"
    job_dir.mkdir(parents=True, exist_ok=True)

    if (cache_dir / "croqui.pdf").exists():
        t = time.perf_counter()
        for name in JOB_ARTIFACTS:
            if (cache_dir / name).exists():
                shutil.copy2(cache_dir / name, job_dir / name)
        tempos["cache"] = time.perf_counter() - t
        return {"sha256": digest, "engine": ENGINE_VERSION, "tempos": tempos, "cached": True}

    t = time.perf_counter()
    if progresso:
        progresso("Lendo projeto")
    extractor = base.get_extractor("projeto_pdf")
    extraction = extractor.extract(digest[:16], caminho_pdf)
    if not extraction.conductors:
        raise ValueError("Projeto sem geometria vetorial de rede")
    (job_dir / "extraction.json").write_text(
        json.dumps(extraction.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tempos["extracao_vetorial"] = time.perf_counter() - t

    t = time.perf_counter()
    render_clean_projeto(
        caminho_pdf,
        extraction,
        job_dir / "clean_projeto.pdf",
        inventory_path=job_dir / "color_inventory.json",
        png_path=job_dir / "clean_projeto.png",
    )
    tempos["limpeza_projeto"] = time.perf_counter() - t

    t = time.perf_counter()
    projeto = interpretar_pdf(
        str(caminho_pdf),
        progresso=progresso,
        additional_image_paths=[str(job_dir / "clean_projeto.png")],
    )
    tempos["interpretacao"] = time.perf_counter() - t

    t = time.perf_counter()
    assert_schema(projeto)
    projeto["viabilidade"] = {"respostas": viability_answers}
    projeto = sanitizar_projeto(projeto)
    (job_dir / "projeto.json").write_text(json.dumps(projeto, ensure_ascii=False, indent=2), encoding="utf-8")
    tempos["sanitizacao"] = time.perf_counter() - t

    t = time.perf_counter()
    if progresso:
        progresso("Finalizando")
    render_croqui_geometrico(
        extraction,
        projeto,
        job_dir / "croqui.pdf",
        selection_path=job_dir / "network_selection.json",
    )
    tempos["geracao_pdf"] = time.perf_counter() - t

    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in JOB_ARTIFACTS:
        if (job_dir / name).exists():
            shutil.copy2(job_dir / name, cache_dir / name)
    tempos["total"] = time.perf_counter() - start
    LOG.info("Tempos do processamento %s: %s", digest, tempos)
    return {"sha256": digest, "engine": ENGINE_VERSION, "tempos": tempos, "cached": False}
