"""
gerador_croqui_v2.py
Gera o croqui usando as posições reais dos equipamentos extraídas do PDF.
A topologia reflete a rede elétrica real (não um layout artificial).
"""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white, red

from extrator_posicional import RedeExtraida, EquipamentoPosicionado
from typing import List, Tuple

COR_VERDE_RGE   = HexColor('#1a5c2a')
COR_VERDE_CLARO = HexColor('#e8f5e9')
COR_TABELA_VERDE = HexColor('#2e7d32')
COR_LINHA_PAR   = HexColor('#90EE90')
COR_LINHA_IMPAR = HexColor('#C8E6C9')
COR_TRABALHO    = red
COR_TR_NOVO     = HexColor('#8B4513')

VIABILIDADE_PERGUNTAS = [
    ("Foi realizada a avaliação do TIPO DE SOLO para permitir executar este Obra ?", "Sim"),
    ("Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos, se estes "
     "apresentam as condições de operação para realizar as Manobras?", "Sim"),
    ("Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor "
     "nos casos de trabalhos de equipes de Linha Viva (Solicitação /DIRA) ?", "Sim"),
    ("Caso seja necessário uma PREPARAÇÃO para execução da Obra, ela já foi realizada?", "Sim"),
    ("Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?", "Sim"),
    ("Se a execução afetar o CLIENTE, ele concorda com a intervenção?", "Sim"),
    ("O MATERIAL para esta obra está disponível?", "Sim"),
    ("O Tempo para execução está adequado e evita possibilidades de ATRASOS na "
     "execução ou no deslocamento para a obra?", "Sim"),
    ("Está previsto outro DOCUMENTO RESERVA para esta obra, que será cancelado "
     "posteriormente?", "Sim"),
    ("Este documento já foi CANCELADO ou é uma Reprogramação?", "Não"),
]


def gerar_croqui(rede: RedeExtraida, caminho_saida: str):
    W, H = landscape(A4)
    c = canvas.Canvas(caminho_saida, pagesize=(W, H))
    MARG = 5 * mm

    _cabecalho(c, W, H, MARG, rede)
    _area_desenho(c, W, H, MARG, rede)
    _tabela_viabilidade(c, W, H, MARG)
    _borda(c, W, H, MARG)

    c.save()
    print(f"Croqui v2 gerado: {caminho_saida}")


# ─────────────────────────────────────────────
#  CABEÇALHO
# ─────────────────────────────────────────────
def _cabecalho(c, W, H, MARG, rede: RedeExtraida):
    CAB_H = 2.1 * cm
    y = H - MARG - CAB_H

    c.setFillColor(HexColor('#f5f5f5'))
    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.rect(MARG, y, W - 2*MARG, CAB_H, fill=1, stroke=1)

    # Linha divisória logo
    c.setLineWidth(0.5)
    c.line(MARG + 2.5*cm, y, MARG + 2.5*cm, y + CAB_H)
    c.line(MARG + 2.5*cm, y + CAB_H/2, W - MARG - 2.5*cm, y + CAB_H/2)

    # Logo RGE
    c.setFillColor(COR_VERDE_RGE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARG + 3*mm, y + 1.5*cm, "RGE")
    c.setFont("Helvetica", 7)
    c.drawString(MARG + 3*mm, y + 1.05*cm, "RioGrandeEnergia")

    # Linha horizontal divisória do logo
    c.line(MARG + 3*mm, y + CAB_H/2, MARG + 2.4*cm, y + CAB_H/2)

    # Título
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W/2, H - MARG - 0.85*cm, "Croqui")

    # Campos
    c.setFont("Helvetica-Bold", 7.5)
    campos = [
        ("Departamento:", rede.departamento,
         MARG + 2.7*cm, y + 1.55*cm),
        ("Município:", rede.municipio,
         MARG + 2.7*cm, y + 0.85*cm),
        ("Equipamento :", rede.equipamento_principal,
         W - MARG - 9*cm, y + 0.85*cm),
        ("Data do Levantamento:", rede.data,
         MARG + 2.7*cm, y + 0.25*cm),
        ("Levantamento de campo realizado por:", "",
         W/2 - 1*cm, y + 0.25*cm),
    ]
    for label, valor, lx, ly in campos:
        c.setFillColor(black)
        c.drawString(lx, ly, label)
        lw = c.stringWidth(label, "Helvetica-Bold", 7.5)
        c.setFont("Helvetica", 7.5)
        c.drawString(lx + lw + 2, ly, valor)
        c.setFont("Helvetica-Bold", 7.5)

    c.setLineWidth(1.5)
    c.line(MARG, y, W - MARG, y)


# ─────────────────────────────────────────────
#  ÁREA DE DESENHO
# ─────────────────────────────────────────────
def _area_desenho(c, W, H, MARG, rede: RedeExtraida):
    CAB_H  = 2.1 * cm
    TAB_H  = 7.0 * cm
    AX = MARG
    AY = MARG + TAB_H
    AW = W - 2*MARG
    AH = H - CAB_H - TAB_H - 2*MARG

    eqs = rede.equipamentos
    if not eqs:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor('#777777'))
        c.drawCentredString(AX + AW/2, AY + AH/2,
            "Nenhum equipamento identificado automaticamente.")
        c.drawCentredString(AX + AW/2, AY + AH/2 - 14,
            "Complete o desenho manualmente no Excel.")
        c.setFillColor(black)
        return

    # ── Escala: mapeia posições do PDF para a área de desenho ──
    PAD = 1.2 * cm
    xs = [e.x for e in eqs]
    ys = [e.y for e in eqs]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    rng_x = max_x - min_x or 1
    rng_y = max_y - min_y or 1

    escala = min(
        (AW - 2*PAD) / rng_x,
        (AH - 2*PAD) / rng_y,
        2.0   # máximo 2.0 pt por pt (evita escala enorme)
    )

    def px(ex):
        return AX + PAD + (ex - min_x) * escala

    def py(ey):
        # PDF y cresce para baixo; croqui y cresce para cima
        return AY + PAD + (max_y - ey) * escala

    # ── Conecta equipamentos por Minimum Spanning Tree (Prim) ──
    arestas = _calcular_mst(eqs, px, py)

    # Desenha conexões
    for a, b, dist in arestas:
        # Linhas de BT (dashed) se tem transformador no trecho
        tem_tr = (a.tipo == "transformador" or b.tipo == "transformador")
        c.setStrokeColor(black)
        c.setLineWidth(0.9)
        if tem_tr:
            c.setDash([5, 3])
        else:
            c.setDash([])
        c.line(px(a.x), py(a.y), px(b.x), py(b.y))

        # Label BT/AT no meio
        mid_x = (px(a.x) + px(b.x)) / 2
        mid_y = (py(a.y) + py(b.y)) / 2 + 3
        c.setDash([])
        c.setFont("Helvetica", 5)
        c.setFillColor(HexColor('#444444'))
        c.drawCentredString(mid_x, mid_y, "BT" if tem_tr else "AT")
        c.setFillColor(black)

    # Área de trabalho (caixa vermelha ao redor dos equipamentos marcados)
    eqs_trab = [e for e in eqs if e.eh_area_trabalho]
    if eqs_trab:
        # Expande para incluir vizinhos próximos também
        eqs_trab_expandido = _expandir_area_trabalho(eqs_trab, eqs)
        _desenhar_area_trabalho(c, eqs_trab_expandido, px, py)

    # Desenha nós
    for eq in eqs:
        _desenhar_no(c, px(eq.x), py(eq.y), eq)

    c.setDash([])
    c.setStrokeColor(black)
    c.setFillColor(black)


def _calcular_mst(eqs: List, px, py) -> list:
    """
    Calcula Minimum Spanning Tree por Prim para conectar os equipamentos.
    Limita distância máxima para não conectar equipamentos muito distantes.
    """
    if len(eqs) < 2:
        return []

    import math

    def dist(a, b):
        return math.sqrt((px(a.x)-px(b.x))**2 + (py(a.y)-py(b.y))**2)

    # Prim's MST usando índices (dataclass não é hashable por padrão)
    visitados = {0}
    nao_visitados = set(range(1, len(eqs)))
    arestas = []
    MAX_DIST = 200  # pts na tela - não conecta se muito longe

    while nao_visitados:
        melhor_i = None
        melhor_j = None
        melhor_dist = float('inf')

        for i in visitados:
            for j in nao_visitados:
                d = dist(eqs[i], eqs[j])
                if d < melhor_dist:
                    melhor_dist = d
                    melhor_i = i
                    melhor_j = j

        if melhor_j is not None and melhor_dist < MAX_DIST:
            arestas.append((eqs[melhor_i], eqs[melhor_j], melhor_dist))
            visitados.add(melhor_j)
            nao_visitados.discard(melhor_j)
        else:
            # Nó isolado
            if nao_visitados:
                j = next(iter(nao_visitados))
                visitados.add(j)
                nao_visitados.discard(j)

    return arestas


def _expandir_area_trabalho(eqs_trab, todos_eqs, raio_pts=60):
    """Inclui vizinhos próximos na área de trabalho."""
    resultado = list(eqs_trab)
    for eq in todos_eqs:
        if eq in resultado:
            continue
        for et in eqs_trab:
            dist = ((eq.x - et.x)**2 + (eq.y - et.y)**2)**0.5
            if dist < raio_pts:
                resultado.append(eq)
                break
    return resultado


def _desenhar_area_trabalho(c, eqs, px_fn, py_fn):
    if not eqs:
        return
    xs = [px_fn(e.x) for e in eqs]
    ys = [py_fn(e.y) for e in eqs]
    pad = 18
    bx = min(xs) - pad
    by = min(ys) - pad
    bw = max(xs) - min(xs) + 2*pad
    bh = max(ys) - min(ys) + 2*pad

    c.setStrokeColor(COR_TRABALHO)
    c.setLineWidth(1.0)
    c.setDash([4, 3])
    c.rect(bx, by, bw, bh, fill=0)
    c.setDash([])
    c.setFont("Helvetica", 6)
    c.setFillColor(COR_TRABALHO)
    c.drawString(bx + 2, by + bh + 2, "Área de trabalho")
    c.setFillColor(black)
    c.setStrokeColor(black)


def _desenhar_no(c, px, py, eq: EquipamentoPosicionado):
    R = 5

    if eq.tipo == "transformador":
        _simbolo_transformador(c, px, py, eq)
    elif eq.tipo == "religador":
        _simbolo_religador(c, px, py, eq)
    elif eq.tipo == "chave":
        _simbolo_chave(c, px, py, eq)
    elif eq.novo:
        _simbolo_triangulo(c, px, py)
    else:
        # Poste existente: círculo com ponto
        c.setStrokeColor(black)
        c.setFillColor(white)
        c.setLineWidth(0.9)
        c.circle(px, py, R, fill=1, stroke=1)
        c.setFillColor(black)
        c.circle(px, py, 1.5, fill=1, stroke=0)

    # Label do ID
    c.setFont("Helvetica", 5.5)
    c.setFillColor(black)
    c.drawCentredString(px, py - R - 7, eq.id)

    if eq.kva > 0:
        kva_str = f"{eq.kva:.0f}kVA"
        c.drawCentredString(px, py - R - 13, kva_str)

    if eq.label_extra:
        c.setFont("Helvetica-Bold", 5.5)
        c.drawCentredString(px, py + R + 5, eq.label_extra[:5])
        c.setFont("Helvetica", 5.5)


def _simbolo_transformador(c, px, py, eq):
    h = 11
    cor = COR_TR_NOVO if eq.novo or eq.eh_area_trabalho else black
    c.setStrokeColor(cor)
    c.setFillColor(white)
    c.setLineWidth(1.1)
    path = c.beginPath()
    path.moveTo(px - 8, py + h/2)
    path.lineTo(px + 8, py + h/2)
    path.lineTo(px, py - h/2)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    # Aterramento
    c.setLineWidth(0.8)
    c.line(px, py - h/2, px, py - h/2 - 5)
    for i, lw in enumerate([8, 5, 2.5]):
        c.line(px - lw, py - h/2 - 5 - i*2, px + lw, py - h/2 - 5 - i*2)
    c.setStrokeColor(black)
    # BT label
    c.setFont("Helvetica-Bold", 5)
    c.setFillColor(HexColor('#555555'))
    c.drawCentredString(px, py + h/2 + 4, "BT")
    c.setFillColor(black)


def _simbolo_religador(c, px, py, eq):
    R = 6
    c.setStrokeColor(black)
    c.setFillColor(white)
    c.setLineWidth(1.0)
    c.circle(px, py, R, fill=1, stroke=1)
    # "R" interno
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(black)
    c.drawCentredString(px, py - 2.5, "R")


def _simbolo_chave(c, px, py, eq):
    S = 6
    c.setStrokeColor(black)
    c.setFillColor(white)
    c.setLineWidth(1.0)
    c.rect(px - S, py - S, 2*S, 2*S, fill=1, stroke=1)
    c.setLineWidth(0.7)
    c.line(px - S*0.7, py - S*0.7, px + S*0.7, py + S*0.7)
    c.line(px - S*0.7, py + S*0.7, px + S*0.7, py - S*0.7)


def _simbolo_triangulo(c, px, py):
    h = 10
    c.setStrokeColor(COR_TR_NOVO)
    c.setFillColor(COR_TR_NOVO)
    c.setLineWidth(0.9)
    path = c.beginPath()
    path.moveTo(px, py + h*0.6)
    path.lineTo(px - 6, py - h*0.4)
    path.lineTo(px + 6, py - h*0.4)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    c.setFillColor(black)
    c.setStrokeColor(black)


# ─────────────────────────────────────────────
#  TABELA VIABILIDADE
# ─────────────────────────────────────────────
def _tabela_viabilidade(c, W, H, MARG):
    TAB_H = 7.0 * cm
    TX = MARG
    TY = MARG
    TW = W - 2*MARG

    # Título
    TITULO_H = 0.55 * cm
    c.setFillColor(COR_TABELA_VERDE)
    c.rect(TX, TY + TAB_H - TITULO_H, TW, TITULO_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(TX + TW*0.35, TY + TAB_H - TITULO_H + 0.15*cm,
                        "Avaliação de Viabilidade")
    c.drawString(TX + TW*0.52, TY + TAB_H - TITULO_H + 0.15*cm,
                 "* Preenchimento obrigatório com Sim, Não ou Não Avaliado")

    # Viabilidade %
    c.setFillColor(HexColor('#1b5e20'))
    c.rect(TX + TW*0.88, TY + TAB_H - TITULO_H, TW*0.12, TITULO_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(TX + TW*0.89, TY + TAB_H - TITULO_H + 0.15*cm, "Viabilidade:")
    c.setFillColor(HexColor('#FFD700'))
    c.drawRightString(TX + TW - 4, TY + TAB_H - TITULO_H + 0.15*cm, "100,0%")

    # Linhas
    N = len(VIABILIDADE_PERGUNTAS)
    LH = (TAB_H - TITULO_H) / N

    for i, (pergunta, resposta) in enumerate(VIABILIDADE_PERGUNTAS):
        ly = TY + TAB_H - TITULO_H - (i+1) * LH
        cor = COR_LINHA_PAR if i % 2 == 0 else COR_LINHA_IMPAR

        c.setFillColor(cor)
        c.rect(TX, ly, TW*0.88, LH, fill=1, stroke=0)
        c.setStrokeColor(HexColor('#4caf50'))
        c.setLineWidth(0.3)
        c.rect(TX, ly, TW*0.88, LH, fill=0, stroke=1)

        c.setFillColor(black)
        c.setFont("Helvetica", 6.5)
        c.drawString(TX + 3, ly + LH*0.28, pergunta[:110])

        # Célula resposta
        RX = TX + TW*0.88
        RW = TW*0.12
        cor_r = COR_TABELA_VERDE if resposta == "Sim" else HexColor('#c62828')
        c.setFillColor(cor_r)
        c.rect(RX, ly, RW, LH, fill=1, stroke=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(RX + RW/2, ly + LH*0.28, resposta)

    c.setFillColor(black)
    c.setStrokeColor(black)


def _borda(c, W, H, MARG):
    c.setStrokeColor(black)
    c.setLineWidth(1.5)
    c.rect(MARG, MARG, W - 2*MARG, H - 2*MARG)
