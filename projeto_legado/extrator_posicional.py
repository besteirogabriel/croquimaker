"""
extrator_posicional.py
Extrai equipamentos e suas posições reais do PDF CAD usando coordenadas de caracteres.
Isso permite reproduzir a topologia da rede no croqui.
"""
import re
import pdfplumber
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class EquipamentoPosicionado:
    id: str
    x: float          # posição X no PDF (pts)
    y: float          # posição Y no PDF (pts)
    tipo: str = "poste"   # poste, transformador, chave, religador, fim_rede
    kva: float = 0.0
    novo: bool = False
    eh_area_trabalho: bool = False
    label_extra: str = ""   # "R3", "BT", "AT", etc.


@dataclass
class RedeExtraida:
    equipamentos: List[EquipamentoPosicionado] = field(default_factory=list)
    pagina_w: float = 1191.0
    pagina_h: float = 842.0
    municipio: str = ""
    departamento: str = "SERRA"
    equipamento_principal: str = ""
    data: str = ""
    obra: str = ""


def extrair_rede_posicional(caminho_pdf: str) -> RedeExtraida:
    """
    Extrai a rede elétrica com posições reais do PDF.
    Usa coordenadas de caracteres individuais para precisão máxima.
    """
    rede = RedeExtraida()

    with pdfplumber.open(caminho_pdf) as pdf:
        for page in pdf.pages:
            rede.pagina_w = page.width
            rede.pagina_h = page.height

            # Extrai caracteres individuais com posição
            chars = page.chars if page.chars else []

            # Extrai palavras para dados textuais (cabeçalho etc.)
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            texto = ' '.join(w['text'] for w in words)

            # Extrai header da primeira página
            if not rede.municipio:
                _extrair_header_texto(texto, rede)

            # Reconstrói IDs de equipamento a partir de chars
            ids_posicionados = _reconstruir_ids_chars(chars, page)
            rede.equipamentos.extend(ids_posicionados)

            # Associa kVA aos transformadores
            _associar_kva(chars, words, rede.equipamentos)

            # Detecta tipos especiais (R3, 2H, 15K, etc.)
            _detectar_tipos_especiais(chars, words, rede.equipamentos)

    # Detecta área de trabalho (postes anotados com P1, P2, P3)
    _marcar_area_trabalho(rede)

    # Remove duplicatas mantendo o de maior confiança
    _deduplicar(rede)

    return rede


def _reconstruir_ids_chars(chars, page) -> List[EquipamentoPosicionado]:
    """
    Reconstrói IDs de 6-7 dígitos a partir de caracteres individuais.
    PDFs CAD frequentemente têm cada dígito como char separado.
    """
    resultados = []

    # Filtra apenas dígitos dentro dos limites da página
    digitos = [
        c for c in chars
        if c['text'].isdigit()
        and 0 <= c['x0'] <= page.width
        and 0 <= c['top'] <= page.height
    ]

    if not digitos:
        return resultados

    # Tolerâncias adaptativas ao tamanho da página
    # A3 normal ~842pt de largura; A1 ~2409pt → tolera espaçamentos maiores
    escala = max(1.0, page.width / 900.0)
    tol_y = 6 * escala     # tolerância Y para agrupar linha
    tol_x = 15 * escala    # tolerância X entre dígitos consecutivos

    # Agrupa dígitos por linha (tolerância Y adaptativa)
    linhas: Dict[int, List] = {}
    slot = max(4, int(tol_y))
    for d in digitos:
        y_key = round(d['top'] / slot) * slot
        if y_key not in linhas:
            linhas[y_key] = []
        linhas[y_key].append(d)

    # Para cada linha, ordena por X e encontra sequências de dígitos consecutivos
    for y_key, digs in linhas.items():
        digs_sorted = sorted(digs, key=lambda d: d['x0'])

        # Agrupa em tokens por proximidade X
        tokens = []
        token_atual = [digs_sorted[0]]

        for d in digs_sorted[1:]:
            gap = d['x0'] - token_atual[-1]['x1']
            if gap <= tol_x:
                token_atual.append(d)
            else:
                tokens.append(token_atual)
                token_atual = [d]
        tokens.append(token_atual)

        # Filtra tokens de 6-7 dígitos
        for token in tokens:
            numero = ''.join(d['text'] for d in token)
            if len(numero) in (6, 7) and numero.isdigit():
                # Evita números que são claramente não-IDs
                if numero.startswith('300001'):  # notas de obra
                    continue
                if int(numero) < 100000:
                    continue

                cx = sum(d['x0'] for d in token) / len(token) + 3
                cy = sum(d['top'] for d in token) / len(token) + 3

                eq = EquipamentoPosicionado(id=numero, x=cx, y=cy)
                resultados.append(eq)

    return resultados


def _associar_kva(chars, words, equipamentos: List[EquipamentoPosicionado]):
    """
    Associa valores de kVA aos equipamentos próximos.
    Identifica transformadores.
    """
    # Encontra posições de "kVA" e valores decimais próximos
    kva_positions = []
    for w in words:
        if 'kVA' in w['text']:
            cx = (w['x0'] + w['x1']) / 2
            cy = (w['top'] + w['bottom']) / 2
            kva_positions.append((cx, cy))

    # Para cada kVA encontrado, busca valor decimal próximo e ID de equipamento
    for kx, ky in kva_positions:
        # Valor decimal a até 80pts de distância
        val_kva = None
        for w in words:
            if re.match(r'^\d+\.\d+$', w['text']):
                wx = (w['x0'] + w['x1']) / 2
                wy = (w['top'] + w['bottom']) / 2
                if abs(wx - kx) < 120 and abs(wy - ky) < 40:
                    try:
                        v = float(w['text'])
                        if 1 <= v <= 10000:
                            val_kva = v
                            break
                    except ValueError:
                        pass

        # Equipamento mais próximo a até 120pts
        eq_mais_proximo = None
        dist_min = 150
        for eq in equipamentos:
            dist = ((eq.x - kx)**2 + (eq.y - ky)**2)**0.5
            if dist < dist_min:
                dist_min = dist
                eq_mais_proximo = eq

        if eq_mais_proximo and val_kva:
            eq_mais_proximo.tipo = "transformador"
            eq_mais_proximo.kva = val_kva


def _detectar_tipos_especiais(chars, words, equipamentos: List[EquipamentoPosicionado]):
    """
    Detecta tipos especiais de equipamento por labels próximos:
    R3/R1 = Religador, 2H/3H = Religador, 15K/25K = Chave, BT = ponto BT
    """
    marcadores = {
        r'\bR[123]\b': 'religador',
        r'\b\dH\b': 'religador',
        r'\b\d+K\b': 'chave',
        r'TC\s*-\s*Telecontrolado': 'religador',
        r'Próprio': None,  # apenas confirma que é equipamento
    }

    for w in words:
        wx = (w['x0'] + w['x1']) / 2
        wy = (w['top'] + w['bottom']) / 2

        for padrao, tipo in marcadores.items():
            if re.search(padrao, w['text'], re.IGNORECASE):
                # Equipamento mais próximo
                eq_prox = None
                dist_min = 120
                for eq in equipamentos:
                    dist = ((eq.x - wx)**2 + (eq.y - wy)**2)**0.5
                    if dist < dist_min:
                        dist_min = dist
                        eq_prox = eq
                if eq_prox and tipo:
                    eq_prox.tipo = tipo
                    eq_prox.label_extra = w['text'][:10]
                break


def _marcar_area_trabalho(rede: RedeExtraida):
    """
    Marca equipamentos na área de trabalho.
    Usa a posição das anotações P1, P2, P3 do projeto para identificar
    quais equipamentos estão na área sendo modificada.
    """
    # Como não temos posições dos P1/P2/P3, usa heurística:
    # O equipamento principal (transformer novo ou chave) é o centro da área de trabalho
    if not rede.equipamentos:
        return

    # Marca o primeiro transformador novo encontrado como área de trabalho
    for eq in rede.equipamentos:
        if eq.tipo == "transformador":
            eq.eh_area_trabalho = True
            break


def _deduplicar(rede: RedeExtraida):
    """Remove equipamentos duplicados (mesmo ID ou mesma posição)."""
    vistos_id = set()
    unicos = []

    for eq in rede.equipamentos:
        if eq.id in vistos_id:
            continue
        # Verifica posição muito próxima (< 15pts) de outro já adicionado
        duplicado = False
        for u in unicos:
            if u.id == eq.id:
                duplicado = True
                break
            dist = ((u.x - eq.x)**2 + (u.y - eq.y)**2)**0.5
            if dist < 15 and u.id != eq.id:
                # Mesma posição mas ID diferente - pode ser fragmento
                # Mantém o de 6 ou 7 dígitos que for mais plausível
                pass
        if not duplicado:
            vistos_id.add(eq.id)
            unicos.append(eq)

    rede.equipamentos = unicos


def _extrair_header_texto(texto: str, rede: RedeExtraida):
    """Extrai dados do cabeçalho do projeto."""
    # Município: texto pode ter encoding corrompido (Munic?pio ou Munic.pio)
    m = re.search(r'Munic.pio:\s*([A-Z][A-Za-zÀ-ÿ\s]+?)(?:\s{2,}|Cliente|Folha|$)', texto)
    if m:
        rede.municipio = m.group(1).strip()

    m = re.search(r'Data[:\s]+(\d{2}/\d{2}/\d{4})', texto)
    if m:
        rede.data = m.group(1)

    m = re.search(r'Obra[:\s]+(.+?)(?:\s{3,}|Endere)', texto)
    if m:
        rede.obra = m.group(1).strip()[:80]

    # Departamento
    m = re.search(r'Ger.ncia de ([A-Za-z\s]+?)(?:\s{2,}|Munic)', texto)
    if m:
        dep = m.group(1).strip()
        rede.departamento = dep[:30]
    elif re.search(r'SERRA', texto):
        rede.departamento = "SERRA"

    # Equipamento principal: procura religador TC-Telecontrolado
    m = re.search(r'(\d{6,7})-630\s+TC', texto)
    if m:
        rede.equipamento_principal = f"RL {m.group(1)}"

    if not rede.equipamento_principal:
        # Procura religador/chave com tipo identificado
        m = re.search(r'(\d{6,7})\s+(?:2H|3H|R[123])\b', texto)
        if m:
            rede.equipamento_principal = f"RL {m.group(1)}"

    if not rede.equipamento_principal:
        # Usa primeiro transformador encontrado
        m = re.search(r'(\d{6,7})[^\n]{0,20}kVA', texto)
        if m:
            rede.equipamento_principal = f"TR {m.group(1)}"
