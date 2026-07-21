from pathlib import Path

from sistema.extractors import base
from sistema.generation.clean_projeto import render_clean_projeto

ext = base.get_extractor("projeto_pdf")
src = Path("Biblioteca/<pasta>/<PROJETO>.pdf")
ex = ext.extract("id", src)
render_clean_projeto(src, ex, Path("saida.pdf"))
