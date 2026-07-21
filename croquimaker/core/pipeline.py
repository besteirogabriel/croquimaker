import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

from .gerador_croqui_v4 import gerar_croqui_v4
from .interpretador_ia import interpretar_pdf
from .schema import assert_schema, sanitizar_projeto

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path("generated/cache")
TEMPLATE_XLS = Path("data/templates/croqui_template.xls")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gerar(caminho_pdf: Path, job_dir: Path, progresso=None) -> dict:
    tempos = {}
    start = time.perf_counter()
    digest = sha256_file(caminho_pdf)
    cache_dir = CACHE_DIR / digest
    job_dir.mkdir(parents=True, exist_ok=True)

    if (cache_dir / "croqui.pdf").exists():
        t = time.perf_counter()
        shutil.copy2(cache_dir / "croqui.pdf", job_dir / "croqui.pdf")
        if (cache_dir / "croqui.xls").exists():
            shutil.copy2(cache_dir / "croqui.xls", job_dir / "croqui.xls")
        tempos["cache"] = time.perf_counter() - t
        return {"sha256": digest, "tempos": tempos, "cached": True}

    t = time.perf_counter()
    projeto = interpretar_pdf(str(caminho_pdf), progresso=progresso)
    tempos["interpretacao"] = time.perf_counter() - t

    t = time.perf_counter()
    assert_schema(projeto)
    projeto = sanitizar_projeto(projeto)
    (job_dir / "projeto.json").write_text(json.dumps(projeto, ensure_ascii=False, indent=2), encoding="utf-8")
    tempos["sanitizacao"] = time.perf_counter() - t

    t = time.perf_counter()
    if progresso:
        progresso("Finalizando")
    gerar_croqui_v4(projeto, str(job_dir / "croqui.pdf"))
    tempos["geracao_pdf"] = time.perf_counter() - t

    t = time.perf_counter()
    if TEMPLATE_XLS.exists():
        shutil.copy2(TEMPLATE_XLS, job_dir / "croqui.xls")
    tempos["excel"] = time.perf_counter() - t

    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(job_dir / "croqui.pdf", cache_dir / "croqui.pdf")
    if (job_dir / "croqui.xls").exists():
        shutil.copy2(job_dir / "croqui.xls", cache_dir / "croqui.xls")
    tempos["total"] = time.perf_counter() - start
    LOG.info("Tempos do processamento %s: %s", digest, tempos)
    return {"sha256": digest, "tempos": tempos, "cached": False}
