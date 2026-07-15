"""
gerador_croqui_v3.py
Gera croqui a partir do payload JSON editado pelo técnico.
Layout: cadeia horizontal linear (estilo croqui RGE real).
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white, red
from reportlab.pdfgen import canvas
from typing import List, Dict

COR_VERDE     = HexColor('#1a5c2a')
COR_VERDE2    = HexColor('#2e7d32')
COR_VERDE_BG  = HexColor('#e8f5e9')
COR_LINHA_PAR = HexColor('#90EE90')
COR_LINHA_IMPAR = HexColor('#C8E6C9')
COR_BORDA_VIAB = HexColor('#4caf50')
COR_TR_NOVO   = HexColor('#8B4513')

VIABILIDADE = [
    ("Foi realizada a avaliação do TIPO DE SOLO para permitir executar este Obra ?", "Sim"),
    ("Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos, se estes apresentam as condições de operação para realizar as Manobras?", "Sim"),
    ("Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor nos casos de trabalhos de equipes de Linha Viva (Solicitação /DIRA) ?", "Sim"),
    ("Caso seja necessário uma PREPARAÇÃO para execução da Obra, ela já foi realizada?", "Sim"),
    ("Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?", "Sim"),
    ("Se a execução afetar o CLIENTE, ele concorda com a intervenção?", "Sim"),
    ("O MATERIAL para esta obra está disponível?", "Sim"),
    ("O Tempo para execução está adequado e evita possibilidades de ATRASOS na execução ou no deslocamento para a obra?", "Sim"),
    ("Está previsto outro DOCUMENTO RESERVA para esta obra, que será cancelado posteriormente?", "Sim"),
    ("Este documento já foi CANCELADO ou é uma Reprogramação?", "Não"),
]


def gerar_croqui_from_payload(payload: dict, caminho_saida: str):
    W, H = landscape(A4)
    MARG = 5 * mm

    c = canvas.Canvas(caminho_saida, pagesize=(W, H))

    _cabecalho(c, W, H, MARG, payload)
    _tabela_viabilidade(c, W, H, MARG)
    _area_desenho(c, W, H, MARG, payload)
    _borda(c, W, H, MARG)

    c.save()
    print(f"[OK] Croqui gerado: {caminho_saida}")


# ─────────────────────────────────────────────
#  CABEÇALHO
# ─────────────────────────────────────────────

def _cabecalho(c, W, H, MARG, p: dict):
    CAB_H = 2.0 * cm
    y = H - MARG - CAB_H

    c.setFillColor(HexColor('#f5f5f5'))
    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.rect(MARG, y, W - 2*MARG, CAB_H, fill=1, stroke=1)

    # Divisória logo | conteúdo
    logo_w = 2.6 * cm
    c.setLineWidth(0.5)
    c.line(MARG + logo_w, y, MARG + logo_w, y + CAB_H)
    c.line(MARG + logo_w, y + CAB_H/2, W - MARG - 2*cm, y + CAB_H/2)

    # Logo RGE
    c.setFillColor(COR_VERDE)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARG + 3*mm, y + 1.4*cm, "RGE")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(HexColor('#444'))
    c.drawString(MARG + 3*mm, y + 1.0*cm, "RioGrandeEnergia")

    # Título CROQUI centralizado
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W/2, H - MARG - 0.8*cm, "Croqui")

    # Linha divisória horizontal do cabeçalho
    c.setLineWidth(0.5)
    c.line(MARG + logo_w, y + CAB_H/2, W - MARG - 2*cm, y + CAB_H/2)

    dep  = p.get('departamento','') or ''
    mun  = p.get('municipio','') or ''
    equip= p.get('equipamento_principal','') or ''
    data = p.get('data','') or ''
    resp = p.get('responsavel','') or ''

    def campo(label, valor, lx, ly):
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(black)
        c.drawString(lx, ly, label)
        lw = c.stringWidth(label, "Helvetica-Bold", 7.5)
        c.setFont("Helvetica", 7.5)
        c.drawString(lx + lw + 2, ly, valor)

    IX = MARG + logo_w + 4
    campo("Departamento:", dep,   IX, y + 1.55*cm)
    campo("Município:",    mun,   IX, y + 0.85*cm)
    campo("Equipamento :", equip, W/2 + 20, y + 0.85*cm)
    campo("Data do Levantamento:", data, IX, y + 0.28*cm)
    campo("Levantamento de campo realizado por:", resp, W/2 + 20, y + 0.28*cm)

    c.setLineWidth(1.5)
    c.line(MARG, y, W - MARG, y)


# ─────────────────────────────────────────────
#  ÁREA DE DESENHO — layout linear
# ─────────────────────────────────────────────

def _area_desenho(c, W, H, MARG, p: dict):
    CAB_H = 2.0 * cm
    TAB_H = 6.8 * cm

    AX = MARG + 4
    AY = MARG + TAB_H + 2
    AW = W - 2*MARG - 8
    AH = H - CAB_H - TAB_H - 2*MARG - 8

    eqs = p.get('equipamentos', [])
    if not eqs:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor('#888'))
        c.drawCentredString(AX + AW/2, AY + AH/2, "Nenhum equipamento informado.")
        c.drawCentredString(AX + AW/2, AY + AH/2 - 14,
            "Adicione os equipamentos no editor e gere novamente.")
        c.setFillColor(black)
        return

    # ── Layout linear: equipamentos em fileira horizontal ──
    # Separa: poste/chave/religador na linha principal; transformadores como ramais
    principais = [e for e in eqs if e.get('tipo') != 'transformador']
    transformadores = [e for e in eqs if e.get('tipo') == 'transformador']

    # Se não houver distinção, trata todos como principais
    if not principais:
        principais = eqs
        transformadores = []

    _desenhar_linha_principal(c, AX, AY, AW, AH, principais, transformadores)


def _desenhar_linha_principal(c, AX, AY, AW, AH, principais, transformadores):
    """Desenha a linha principal horizontal com transformadores como ramais abaixo."""
    N = len(principais)
    if N == 0:
        return

    # Espaçamento horizontal entre equipamentos
    PAD_H = 1.5 * cm
    espaco = min((AW - 2*PAD_H) / max(N - 1, 1), 3.5*cm)
    total_w = espaco * (N - 1)
    inicio_x = AX + (AW - total_w) / 2
    linha_y  = AY + AH * 0.52   # linha principal na metade superior

    # Desenha linha AT conectando todos
    c.setStrokeColor(black)
    c.setLineWidth(1.2)
    c.setDash([])
    for i in range(N - 1):
        x1 = inicio_x + i * espaco
        x2 = inicio_x + (i+1) * espaco
        c.line(x1, linha_y, x2, linha_y)
        # Label AT no meio
        mid_x = (x1 + x2) / 2
        c.setFont("Helvetica", 5.5)
        c.setFillColor(HexColor('#444'))
        c.drawCentredString(mid_x, linha_y + 4, "AT")
        c.setFillColor(black)

    # Desenha cada equipamento principal
    for i, eq in enumerate(principais):
        ex = inicio_x + i * espaco
        _simbolo(c, ex, linha_y, eq)

    # Transformadores: ramais abaixo de um dos equipamentos principais
    ramal_y = linha_y - 2.8*cm
    for j, tr in enumerate(transformadores):
        # Associa ao equipamento principal mais próximo pelo índice
        idx = min(j, N - 1)
        tx = inicio_x + idx * espaco
        # Linha BT vertical descendo
        c.setStrokeColor(black)
        c.setLineWidth(0.9)
        c.setDash([5, 3])
        c.line(tx, linha_y - 12, tx, ramal_y + 14)
        c.setDash([])
        # Label BT
        c.setFont("Helvetica", 5.5)
        c.setFillColor(HexColor('#555'))
        c.drawCentredString(tx + 14, ramal_y + 30, "BT")
        c.setFillColor(black)
        # Símbolo do transformador
        _simbolo(c, tx, ramal_y, tr)

    # Área de trabalho (retângulo vermelho pontilhado)
    # Ao redor do transformador/religador/chave central
    eqs_principais = [e for e in principais
                      if e.get('tipo') in ('transformador','religador','chave')]
    if not eqs_principais and transformadores:
        eqs_principais = transformadores[:1]
    if eqs_principais:
        # Usa a posição do primeiro equipamento especial
        idx_central = principais.index(eqs_principais[0]) if eqs_principais[0] in principais else 0
        cx = inicio_x + idx_central * espaco
        pad = 30
        c.setStrokeColor(red)
        c.setLineWidth(1.0)
        c.setDash([4, 3])
        # Retângulo inclui principal + transformador se houver
        by = ramal_y - pad if transformadores else linha_y - pad
        bh = linha_y + pad - by
        c.rect(cx - pad, by, 2*pad, bh, fill=0)
        c.setDash([])
        c.setFont("Helvetica", 6)
        c.setFillColor(red)
        c.drawString(cx - pad + 2, by + bh + 2, "Área de trabalho")
        c.setFillColor(black)
        c.setStrokeColor(black)


def _simbolo(c, px, py, eq: dict):
    tipo  = eq.get('tipo', 'poste')
    novo  = eq.get('novo', False)
    label = eq.get('label', '') or ''
    kva   = eq.get('kva', 0) or 0
    eid   = eq.get('id', '') or ''

    if tipo == 'transformador':
        _draw_transformador(c, px, py, novo, kva, label)
    elif tipo == 'religador':
        _draw_religador(c, px, py, label)
    elif tipo == 'chave':
        _draw_chave(c, px, py, label)
    elif novo:
        _draw_triangulo(c, px, py)
    else:
        _draw_poste(c, px, py)

    # Label ID abaixo do símbolo
    c.setFont("Helvetica", 6)
    c.setFillColor(black)
    c.drawCentredString(px, py - 18, eid)

    if kva > 0:
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(px, py - 25, f"{kva:.0f}kVA")

    if label and tipo not in ('transformador',):
        c.setFont("Helvetica-Bold", 5.5)
        c.setFillColor(HexColor('#333'))
        c.drawCentredString(px, py + 18, label)
        c.setFillColor(black)


def _draw_poste(c, px, py):
    R = 7
    c.setStrokeColor(black); c.setFillColor(white); c.setLineWidth(1.0)
    c.circle(px, py, R, fill=1, stroke=1)
    c.setFillColor(black)
    c.circle(px, py, 1.8, fill=1, stroke=0)


def _draw_transformador(c, px, py, novo, kva, label):
    h = 14
    cor = COR_TR_NOVO if novo else black
    c.setStrokeColor(cor); c.setFillColor(white); c.setLineWidth(1.1)
    path = c.beginPath()
    path.moveTo(px - 9, py + h/2)
    path.lineTo(px + 9, py + h/2)
    path.lineTo(px, py - h/2)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    # Aterramento
    c.setLineWidth(0.8); c.setStrokeColor(cor)
    base_y = py - h/2
    c.line(px, base_y, px, base_y - 6)
    for i, lw in enumerate([9, 6, 3]):
        c.line(px-lw, base_y-6-i*2.5, px+lw, base_y-6-i*2.5)
    c.setStrokeColor(black)
    # BT label acima
    c.setFont("Helvetica-Bold", 5); c.setFillColor(HexColor('#555'))
    c.drawCentredString(px, py + h/2 + 4, "BT")
    c.setFillColor(black)


def _draw_religador(c, px, py, label):
    R = 8
    c.setStrokeColor(black); c.setFillColor(white); c.setLineWidth(1.0)
    c.circle(px, py, R, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 7); c.setFillColor(black)
    c.drawCentredString(px, py - 2.5, "R")


def _draw_chave(c, px, py, label):
    S = 7
    c.setStrokeColor(black); c.setFillColor(white); c.setLineWidth(1.0)
    c.rect(px - S, py - S, 2*S, 2*S, fill=1, stroke=1)
    c.setLineWidth(0.7)
    c.line(px - S*0.7, py - S*0.7, px + S*0.7, py + S*0.7)
    c.line(px - S*0.7, py + S*0.7, px + S*0.7, py - S*0.7)


def _draw_triangulo(c, px, py):
    h = 12
    c.setStrokeColor(COR_TR_NOVO); c.setFillColor(COR_TR_NOVO); c.setLineWidth(0.9)
    path = c.beginPath()
    path.moveTo(px, py + h*0.6)
    path.lineTo(px - 7, py - h*0.4)
    path.lineTo(px + 7, py - h*0.4)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    c.setFillColor(black); c.setStrokeColor(black)


# ─────────────────────────────────────────────
#  TABELA DE VIABILIDADE
# ─────────────────────────────────────────────

def _tabela_viabilidade(c, W, H, MARG):
    TAB_H = 6.8 * cm
    TX = MARG; TY = MARG; TW = W - 2*MARG
    N = len(VIABILIDADE)
    TITULO_H = 0.55 * cm
    LH = (TAB_H - TITULO_H) / N

    # Título
    c.setFillColor(COR_VERDE2)
    c.rect(TX, TY + TAB_H - TITULO_H, TW * 0.88, TITULO_H, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 8)
    c.drawString(TX + 4, TY + TAB_H - TITULO_H + 3,
                 "Avaliação de Viabilidade")
    c.setFont("Helvetica", 7)
    c.drawString(TX + TW*0.25, TY + TAB_H - TITULO_H + 3,
                 "* Preenchimento obrigatório com Sim, Não ou Não Avaliado")

    # Viabilidade %
    c.setFillColor(HexColor('#1b5e20'))
    c.rect(TX + TW*0.88, TY + TAB_H - TITULO_H, TW*0.12, TITULO_H, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 7)
    c.drawString(TX + TW*0.89, TY + TAB_H - TITULO_H + 3, "Viabilidade:")
    c.setFillColor(HexColor('#FFD700'))
    c.drawRightString(TX + TW - 3, TY + TAB_H - TITULO_H + 3, "100,0%")

    # Linhas
    for i, (pergunta, resp) in enumerate(VIABILIDADE):
        ly = TY + TAB_H - TITULO_H - (i+1)*LH
        cor = COR_LINHA_PAR if i % 2 == 0 else COR_LINHA_IMPAR

        c.setFillColor(cor)
        c.rect(TX, ly, TW*0.88, LH, fill=1, stroke=0)
        c.setStrokeColor(COR_BORDA_VIAB); c.setLineWidth(0.3)
        c.rect(TX, ly, TW*0.88, LH, fill=0, stroke=1)

        c.setFillColor(black); c.setFont("Helvetica", 6.5)
        c.drawString(TX + 3, ly + LH*0.28, pergunta[:115])

        # Resposta
        RX = TX + TW*0.88; RW = TW*0.12
        cor_r = COR_VERDE2 if resp == 'Sim' else HexColor('#c62828')
        c.setFillColor(cor_r)
        c.rect(RX, ly, RW, LH, fill=1, stroke=1)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(RX + RW/2, ly + LH*0.28, resp)

    c.setFillColor(black); c.setStrokeColor(black)


def _borda(c, W, H, MARG):
    c.setStrokeColor(black); c.setLineWidth(1.5)
    c.rect(MARG, MARG, W - 2*MARG, H - 2*MARG)
