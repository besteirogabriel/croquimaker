"""
extrator_v3.py — Extração de equipamentos usando PyMuPDF (fitz).
Melhor que pdfplumber para PDFs CAD da CPFL/RGE.
"""
import re
import fitz   # PyMuPDF
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Equipamento:
    id: str
    x: float          # posição X no PDF (pts)
    y: float          # posição Y no PDF (pts)
    tipo: str = "poste"         # poste | transformador | chave | religador
    kva: float = 0.0
    label: str = ""             # ex: "R3", "15K", "BT"
    novo: bool = False
    area_trabalho: bool = False


@dataclass
class DadosExtraidos:
    equipamentos: List[Equipamento] = field(default_factory=list)
    municipio: str = ""
    departamento: str = "SERRA"
    equipamento_principal: str = ""
    data: str = ""
    obra: str = ""
    pagina_w: float = 1190.0
    pagina_h: float = 841.0


# ─────────────────────────────────────────────────────────────
#  FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────────────────────────

def extrair_dados(caminho_pdf: str) -> DadosExtraidos:
    dados = DadosExtraidos()

    doc = fitz.open(caminho_pdf)
    todos_spans = []

    for page_num, page in enumerate(doc):
        dados.pagina_w = page.rect.width
        dados.pagina_h = page.rect.height

        # Extrai spans de texto com posição
        dict_data = page.get_text('dict')
        for block in dict_data.get('blocks', []):
            if block.get('type') != 0:
                continue
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    t = span.get('text', '').strip()
                    if not t:
                        continue
                    bbox = span.get('bbox', (0, 0, 0, 0))
                    todos_spans.append({
                        'text': t,
                        'cx': (bbox[0] + bbox[2]) / 2,
                        'cy': (bbox[1] + bbox[3]) / 2,
                        'x0': bbox[0], 'y0': bbox[1],
                        'x1': bbox[2], 'y1': bbox[3],
                        'page': page_num,
                    })

        # Extrai palavras também (diferente agrupamento)
        words = page.get_text('words')
        for w in words:
            x0, y0, x1, y1, texto = w[0], w[1], w[2], w[3], w[4]
            if texto.strip():
                todos_spans.append({
                    'text': texto.strip(),
                    'cx': (x0 + x1) / 2,
                    'cy': (y0 + y1) / 2,
                    'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                    'page': page_num,
                })

    doc.close()

    # Extrai cabeçalho
    texto_completo = ' '.join(s['text'] for s in todos_spans)
    _extrair_cabecalho(texto_completo, dados)

    # Encontra equipamentos com ID de 6-7 dígitos
    _extrair_equipamentos(todos_spans, dados)

    return dados


# ─────────────────────────────────────────────────────────────
#  CABEÇALHO
# ─────────────────────────────────────────────────────────────

def _extrair_cabecalho(texto: str, dados: DadosExtraidos):
    # Município
    m = re.search(r'Munic.pio[:\s]+([A-Z][A-Za-z\s]+?)(?:\s{2,}|Cliente|Folha|Ger.ncia|$)', texto)
    if m:
        dados.municipio = m.group(1).strip()

    # Data
    m = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', texto)
    if m:
        dados.data = m.group(1)

    # Departamento / Gerência
    m = re.search(r'Ger.ncia de ([^\s][^.]{3,40}?)(?:\s{2,}|Munic)', texto)
    if m:
        dados.departamento = m.group(1).strip()[:30]
    elif 'SERRA' in texto:
        dados.departamento = 'SERRA'

    # Equipamento principal: religador TC
    m = re.search(r'(\d{6,7})-630\s*TC', texto)
    if m:
        dados.equipamento_principal = f"RL {m.group(1)}"

    # Religador por tipo (2H, R3, etc.)
    if not dados.equipamento_principal:
        m = re.search(r'(\d{6,7})\s+(?:2H|3H|R[123])\b', texto)
        if m:
            dados.equipamento_principal = f"RL {m.group(1)}"

    # Transformador
    if not dados.equipamento_principal:
        m = re.search(r'(\d{6,7})\s+[\d.]+\s*kVA', texto)
        if m:
            dados.equipamento_principal = f"TR {m.group(1)}"


# ─────────────────────────────────────────────────────────────
#  EQUIPAMENTOS
# ─────────────────────────────────────────────────────────────

def _extrair_equipamentos(spans: list, dados: DadosExtraidos):
    vistos: Dict[str, Equipamento] = {}

    for span in spans:
        txt = span['text']
        cx = span['cx']
        cy = span['cy']
        pg = span['page']

        # Procura IDs de 6-7 dígitos no texto do span
        for m in re.finditer(r'\b(\d{6,7})\b', txt):
            num = m.group(1)
            if int(num) < 100000:
                continue
            # Filtra números de nota/documento
            if num.startswith('300001') or num.startswith('30000'):
                continue

            if num in vistos:
                continue   # já adicionado

            eq = Equipamento(id=num, x=cx, y=cy)

            # Detecta tipo pelo contexto no span
            if re.search(r'\bkVA\b', txt, re.I):
                eq.tipo = 'transformador'
                m_kva = re.search(r'([\d.]+)\s*kVA', txt)
                if m_kva:
                    try:
                        eq.kva = float(m_kva.group(1))
                    except ValueError:
                        pass
            elif re.search(r'\b(TC|2H|3H|R[123]|Telecontrolado)\b', txt, re.I):
                eq.tipo = 'religador'
                m_lab = re.search(r'\b(2H|3H|R[123]|TC)\b', txt)
                if m_lab:
                    eq.label = m_lab.group(1)
            elif re.search(r'\b(\d+K)\b', txt):
                eq.tipo = 'chave'
                m_lab = re.search(r'\b(\d+K)\b', txt)
                if m_lab:
                    eq.label = m_lab.group(1)

            # Procura contexto nos spans vizinhos (raio de 80 pts)
            if eq.tipo == 'poste':
                ctx = _spans_vizinhos(cx, cy, spans, raio=80)
                if re.search(r'\bkVA\b', ctx, re.I):
                    eq.tipo = 'transformador'
                    m_kva = re.search(r'([\d.]+)\s*kVA', ctx)
                    if m_kva:
                        try:
                            eq.kva = float(m_kva.group(1))
                        except ValueError:
                            pass
                elif re.search(r'\b(TC|2H|3H|R[123]|Telecontrolado)\b', ctx, re.I):
                    eq.tipo = 'religador'
                    m_lab = re.search(r'\b(2H|3H|R[123]|TC)\b', ctx)
                    if m_lab:
                        eq.label = m_lab.group(1)
                elif re.search(r'\b(\d+K)\b', ctx):
                    eq.tipo = 'chave'
                    m_lab = re.search(r'\b(\d+K)\b', ctx)
                    if m_lab:
                        eq.label = m_lab.group(1)

            vistos[num] = eq

    # Ordena por posição Y depois X (leitura natural)
    equipamentos = sorted(vistos.values(), key=lambda e: (e.y, e.x))

    # Marca área de trabalho: equipamentos do "Plano de Execução"
    # (o que está mais central na página = mais provável de ser o foco)
    if equipamentos:
        cx_med = sum(e.x for e in equipamentos) / len(equipamentos)
        cy_med = sum(e.y for e in equipamentos) / len(equipamentos)
        for eq in equipamentos:
            dist = ((eq.x - cx_med)**2 + (eq.y - cy_med)**2)**0.5
            if dist < 100 and eq.tipo in ('transformador', 'religador', 'chave'):
                eq.area_trabalho = True

    dados.equipamentos = equipamentos


def _spans_vizinhos(cx: float, cy: float, spans: list, raio: float) -> str:
    """Retorna texto concatenado dos spans dentro do raio."""
    partes = []
    for s in spans:
        dist = ((s['cx'] - cx)**2 + (s['cy'] - cy)**2)**0.5
        if dist < raio:
            partes.append(s['text'])
    return ' '.join(partes)
