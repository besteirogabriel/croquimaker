"""
gerador_croqui_v4.py — Gerador de croqui ortogonal RGE/CPFL.
Layout: tronco horizontal central + ramais perpendiculares (acima/abaixo).
"""
import os, json, re
from collections import defaultdict, deque
from typing import Optional

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm

# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────
PW, PH   = landscape(A3)   # ~1191 × 842 pt
MARGIN   = 12 * mm         # margem
STEP_H   = 50              # espaço horizontal entre nós (pt)
STEP_V   = 55              # espaço vertical entre nós de ramos
NODE_R   = 4               # raio do círculo do poste
FONT_PT  = 6               # tamanho base dos labels

# Cabeçalho (simula tabela real RGE)
HEADER_H = 28 * mm

# Cores
C_MT     = HexColor("#1565C0")   # azul – MT existente
C_BT     = HexColor("#2E7D32")   # verde – BT existente
C_NOVA   = HexColor("#E65100")   # laranja – rede nova
C_RECON  = HexColor("#6A1B9A")   # roxo – recondutorada
C_AUX    = HexColor("#90A4AE")   # cinza
C_NOVO   = HexColor("#C62828")   # vermelho – poste novo
C_EXIST  = black
C_TR     = HexColor("#E65100")
C_FU     = HexColor("#1565C0")
C_RL     = HexColor("#6A1B9A")
C_AT     = HexColor("#33691E")
C_DEL    = HexColor("#B71C1C")
C_VERDE  = HexColor("#1a5c2a")
C_VERDE2 = HexColor("#e8f5e9")


# ─────────────────────────────────────────────
#  ENTRADA PÚBLICA
# ─────────────────────────────────────────────

def gerar_croqui_v4(projeto_json: dict, caminho_saida: str) -> str:
    meta  = projeto_json.get("meta", {})
    if not isinstance(meta, dict): meta = {}

    nos_raw = projeto_json.get("nos", [])
    trs_raw = projeto_json.get("trechos", [])
    if not isinstance(nos_raw, list): nos_raw = list(nos_raw.values()) if isinstance(nos_raw, dict) else []
    if not isinstance(trs_raw, list): trs_raw = list(trs_raw.values()) if isinstance(trs_raw, dict) else []

    nos = {n["id"]: n for n in nos_raw if isinstance(n, dict) and n.get("id")}
    trechos = [t for t in trs_raw if isinstance(t, dict)]

    posicoes = _calcular_layout(nos, trechos)

    c = rl_canvas.Canvas(caminho_saida, pagesize=(PW, PH))
    _draw_header(c, meta)
    _draw_croqui(c, nos, trechos, posicoes)
    c.save()
    return caminho_saida


def gerar_croqui_from_json_file(caminho_json: str, caminho_saida: str) -> str:
    with open(caminho_json, encoding="utf-8") as f:
        p = json.load(f)
    return gerar_croqui_v4(p, caminho_saida)


# ─────────────────────────────────────────────
#  LAYOUT ORTOGONAL
# ─────────────────────────────────────────────

def _pid(s: str) -> int:
    m = re.search(r'\d+', str(s))
    return int(m.group()) if m else 0


def _calcular_layout(nos: dict, trechos: list) -> dict:
    if not nos:
        return {}

    # Pegar posições já explícitas no JSON (x,y não vazias)
    pos = {}
    for nid, n in nos.items():
        try:
            xv = str(n.get("x", "")).strip()
            yv = str(n.get("y", "")).strip()
            if xv and yv and xv not in ("0", "") and yv not in ("0", ""):
                pos[nid] = (float(xv), float(yv))
        except (ValueError, TypeError):
            pass

    # Se todas as posições estão definidas, retorna
    if len(pos) == len(nos):
        return _normalizar(pos)

    # Construir grafo de adjacência
    adj = defaultdict(set)
    for t in trechos:
        a = str(t.get("de", ""))
        b = str(t.get("para", ""))
        if a in nos and b in nos:
            adj[a].add(b)
            adj[b].add(a)

    # Nós sem posição definida
    sem_pos = set(nid for nid in nos if nid not in pos)
    if not sem_pos:
        return _normalizar(pos)

    # Componentes conexas dos nós sem posição
    visitados = set()
    offset_x = 0

    for inicio in sorted(sem_pos, key=_pid):
        if inicio in visitados:
            continue

        # BFS para pegar componente
        comp = []
        q = deque([inicio])
        visitados.add(inicio)
        while q:
            cur = q.popleft()
            comp.append(cur)
            for viz in adj[cur]:
                if viz in sem_pos and viz not in visitados:
                    visitados.add(viz)
                    q.append(viz)

        comp_set = set(comp)

        if len(comp) == 1:
            pos[comp[0]] = (offset_x, 0)
            offset_x += STEP_H * 2
            continue

        # Encontrar tronco (caminho mais longo)
        extremo1 = _bfs_extremo(comp[0], adj, comp_set)
        extremo2 = _bfs_extremo(extremo1, adj, comp_set)
        tronco   = _caminho(extremo1, extremo2, adj, comp_set)
        tronco_s = set(tronco)

        # Posicionar tronco horizontalmente
        for i, nid in enumerate(tronco):
            pos[nid] = (offset_x + i * STEP_H, 0.0)

        # Posicionar ramais
        _ramais(tronco, tronco_s, adj, comp_set, pos)

        # Avançar offset para próxima componente
        xs = [pos[n][0] for n in comp if n in pos]
        offset_x = (max(xs) if xs else offset_x) + STEP_H * 3

    return _normalizar(pos)


def _bfs_extremo(start: str, adj: dict, comp: set) -> str:
    dist = {start: 0}
    q = deque([start])
    ultimo = start
    while q:
        cur = q.popleft()
        ultimo = cur
        for viz in adj[cur]:
            if viz in comp and viz not in dist:
                dist[viz] = dist[cur] + 1
                q.append(viz)
    return ultimo


def _caminho(start: str, end: str, adj: dict, comp: set) -> list:
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == end:
            break
        for viz in sorted(adj[cur], key=_pid):
            if viz in comp and viz not in prev:
                prev[viz] = cur
                q.append(viz)
    if end not in prev:
        return [start]
    path, cur = [], end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def _ramais(tronco: list, tronco_s: set, adj: dict, comp_s: set, pos: dict):
    """
    Posiciona ramais perpendicularmente ao tronco:
    - Primeiro nó do ramal: mesmo x do nó do tronco, y ± STEP_V
    - Nós seguintes do ramal: avançam horizontalmente no mesmo y
    """
    processados = set(tronco_s)
    # Conta quantos ramais saem para cima/baixo de cada nó do tronco
    lado_cima = defaultdict(int)
    lado_baixo = defaultdict(int)

    fila = deque()

    for nid in tronco:
        vizinhos_ramal = sorted(
            [v for v in adj[nid] if v not in processados and v in comp_s],
            key=_pid
        )
        for viz in vizinhos_ramal:
            if viz in processados:
                continue
            processados.add(viz)
            # Alterna cima/baixo pelo número de ramais já alocados neste nó
            total = lado_cima[nid] + lado_baixo[nid]
            acima = (total % 2 == 0)
            if acima:
                lado_cima[nid] += 1
            else:
                lado_baixo[nid] += 1
            # Primeiro passo: vertical
            fila.append((nid, viz, acima, False))  # False = primeiro passo (vertical)

    while fila:
        pai, cur, acima, horizontal = fila.popleft()
        px, py = pos[pai]

        if horizontal:
            # Continua horizontalmente no mesmo nível do ramal
            pos[cur] = (px + STEP_H, py)
        else:
            # Primeiro passo: perpendicular ao tronco
            dy = STEP_V * (1 if acima else -1)
            pos[cur] = (px, py + dy)

        # Próximos nós do ramal continuam horizontalmente
        vizinhos = sorted(
            [v for v in adj[cur] if v not in processados and v in comp_s],
            key=_pid
        )
        for viz in vizinhos:
            if viz in processados:
                continue
            processados.add(viz)
            fila.append((cur, viz, acima, True))  # True = continua horizontal


def _normalizar(pos: dict) -> dict:
    if not pos:
        return pos
    min_x = min(v[0] for v in pos.values())
    min_y = min(v[1] for v in pos.values())
    return {k: (float(v[0] - min_x), float(v[1] - min_y)) for k, v in pos.items()}


# ─────────────────────────────────────────────
#  CABEÇALHO
# ─────────────────────────────────────────────

def _draw_header(c, meta: dict):
    """Cabeçalho no topo da página, estilo tabela RGE."""
    hx = MARGIN
    hy = PH - MARGIN - HEADER_H
    hw = PW - 2 * MARGIN

    # Fundo verde escuro
    c.setFillColor(C_VERDE)
    c.rect(hx, hy + HEADER_H * 0.55, hw, HEADER_H * 0.45, fill=1, stroke=0)

    # Título
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(hx + 8, hy + HEADER_H * 0.7, "Croqui de Projeto Elétrico  RGE/CPFL")

    # Linha inferior de campos (fundo cinza claro)
    c.setFillColor(C_VERDE2)
    c.rect(hx, hy, hw, HEADER_H * 0.55, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#c8e6c9"))
    c.setLineWidth(0.5)
    c.rect(hx, hy, hw, HEADER_H * 0.55, fill=0, stroke=1)

    # Campos
    campos = [
        ("OS", meta.get("os", "")),
        ("Tipo", meta.get("tipo", "")),
        ("Município", meta.get("municipio", "")),
        ("Departamento", meta.get("departamento", "")),
        ("Equipamento", meta.get("equipamento", "")),
        ("Data", meta.get("data_levantamento", "")),
        ("Responsável", meta.get("responsavel", "")),
    ]
    n = len(campos)
    cw = hw / n
    c.setFillColor(HexColor("#1b5e20"))
    c.setFont("Helvetica-Bold", 6.5)
    for i, (label, valor) in enumerate(campos):
        cx = hx + i * cw
        c.drawString(cx + 4, hy + HEADER_H * 0.38, label)
        c.setFont("Helvetica", 7)
        c.setFillColor(black)
        c.drawString(cx + 4, hy + HEADER_H * 0.12, str(valor)[:28])
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(HexColor("#1b5e20"))
        if i > 0:
            c.setStrokeColor(HexColor("#c8e6c9"))
            c.setLineWidth(0.5)
            c.line(cx, hy, cx, hy + HEADER_H * 0.55)


# ─────────────────────────────────────────────
#  DESENHO PRINCIPAL
# ─────────────────────────────────────────────

def _area_desenho():
    """Retorna (x0, y0, x1, y1) da área de desenho (abaixo do cabeçalho)."""
    return (MARGIN, MARGIN, PW - MARGIN, PH - MARGIN - HEADER_H - 4 * mm)


def _escala(posicoes: dict):
    """Calcula scale, tx, ty para encaixar o grafo na área de desenho."""
    x0, y0, x1, y1 = _area_desenho()
    aw = x1 - x0 - 2 * MARGIN
    ah = y1 - y0 - 2 * MARGIN

    if not posicoes:
        return 1.0, x0 + MARGIN, y0 + ah / 2

    xs = [v[0] for v in posicoes.values()]
    ys = [v[1] for v in posicoes.values()]
    rw = max(xs) - min(xs) or 1
    rh = max(ys) - min(ys) or 1

    scale = min(aw / rw, ah / rh, 2.5)
    scale = max(scale, 0.25)

    # Centralizar
    tx = x0 + MARGIN + (aw - rw * scale) / 2 - min(xs) * scale
    ty = y0 + MARGIN + (ah - rh * scale) / 2 - min(ys) * scale

    return scale, tx, ty


def _C(x, y, scale, tx, ty):
    return float(tx + x * scale), float(ty + y * scale)


def _draw_croqui(c, nos: dict, trechos: list, posicoes: dict):
    if not posicoes:
        c.setFont("Helvetica", 11)
        c.setFillColor(black)
        x0, y0, x1, y1 = _area_desenho()
        c.drawCentredString((x0+x1)/2, (y0+y1)/2, "Nenhum nó identificado no projeto.")
        return

    scale, tx, ty = _escala(posicoes)

    # — Trechos —
    for t in trechos:
        de = t.get("de",""); para = t.get("para","")
        if de not in posicoes or para not in posicoes:
            continue
        try:
            cx1,cy1 = _C(posicoes[de][0],  posicoes[de][1],  scale, tx, ty)
            cx2,cy2 = _C(posicoes[para][0], posicoes[para][1], scale, tx, ty)
        except Exception:
            continue

        tipo = str(t.get("tipo","MT")).upper()
        cor, lw, dash = _estilo_trecho(tipo)
        c.setStrokeColor(cor); c.setLineWidth(lw)
        c.setDash(*dash) if dash else c.setDash()

        # Linha ortogonal: horizontal → depois vertical
        if abs(cx2-cx1) > 1 and abs(cy2-cy1) > 1:
            c.line(cx1, cy1, cx2, cy1)
            c.line(cx2, cy1, cx2, cy2)
        else:
            c.line(cx1, cy1, cx2, cy2)
        c.setDash()

        # Label do cabo (ao centro, deslocado para não sobrepor linha)
        cabo = str(t.get("cabo","")).strip()
        if cabo and scale > 0.4:
            try:
                mx = float((cx1+cx2)/2)
                my = float(cy1) + 3
                c.setFont("Helvetica", max(4, min(6, int(scale*3))))
                c.setFillColor(cor)
                c.drawCentredString(mx, my, cabo[:18])
            except Exception:
                pass

    # — Nós —
    for nid, pxy in posicoes.items():
        if nid not in nos:
            continue
        no = nos[nid]
        try:
            cx, cy = _C(pxy[0], pxy[1], scale, tx, ty)
        except Exception:
            continue
        _draw_no(c, cx, cy, nid, no, scale)


def _draw_no(c, cx, cy, nid, no: dict, scale: float):
    r = max(3, min(NODE_R, int(scale * 2.5)))
    novo = "NOVO" in str(no.get("tipo","")).upper()

    c.setLineWidth(1.0)
    if novo:
        c.setFillColor(C_NOVO); c.setStrokeColor(C_NOVO)
        c.circle(cx, cy, r, fill=1, stroke=1)
    else:
        c.setFillColor(white); c.setStrokeColor(C_EXIST)
        c.circle(cx, cy, r, fill=1, stroke=1)

    # Label do nó (abaixo do círculo)
    label = str(no.get("label") or nid)
    fs = max(4, min(6, int(scale*3)))
    c.setFont("Helvetica", fs)
    c.setFillColor(black)
    c.drawCentredString(cx, cy - r - fs - 1, label)

def _estilo_trecho(tipo: str):
    if "RECOND" in tipo:  return C_RECON, 1.4, (8,3)
    if "NOVA"  in tipo:   return C_NOVA,  1.3, None
    if "COMPL" in tipo:   return C_NOVA,  1.1, (4,2)
    if tipo.startswith("BT"): return C_BT, 1.0, (5,3)
    if tipo == "AUX":     return C_AUX,  0.6, (2,2)
    return C_MT, 1.4, None


# ─────────────────────────────────────────────
#  LEGENDA
# ─────────────────────────────────────────────

def _draw_legenda(c):
    lw, lh = 100, 100
    x0 = PW - MARGIN - lw
    y0 = MARGIN

    c.setFillColor(HexColor("#FAFAFA"))
    c.setStrokeColor(HexColor("#CCCCCC"))
    c.setLineWidth(0.4)
    c.rect(x0, y0, lw, lh, fill=1, stroke=1)

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(black)
    c.drawString(x0+4, y0+lh-10, "LEGENDA")

    itens = [
        (C_MT,   1.4, None,  "MT existente"),
        (C_BT,   1.0, (5,3), "BT existente"),
        (C_NOVA, 1.3, None,  "Rede nova"),
        (C_RECON,1.4, (8,3), "Recondutorada"),
        (C_EXIST,1.0, None,  "Poste exist. ○"),
        (C_NOVO, 1.0, None,  "Poste novo ●"),
        (C_TR,   1.0, None,  "TR Transformador"),
        (C_FU,   1.0, None,  "FU Chave fusível"),
        (C_RL,   1.0, None,  "RL Religador"),
        (C_AT,   1.0, None,  "AT Aterramento"),
    ]
    y = y0 + lh - 20
    for cor, lw2, dash, nome in itens:
        c.setStrokeColor(cor); c.setFillColor(cor); c.setLineWidth(lw2)
        c.setDash(*dash) if dash else c.setDash()
        c.line(x0+4, y+2, x0+16, y+2)
        c.setDash()
        c.setFont("Helvetica", 5.5)
        c.drawString(x0+19, y, nome)
        y -= 8
