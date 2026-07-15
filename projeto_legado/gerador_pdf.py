"""
gerador_pdf.py - Gera o croqui no formato RGE/CPFL como PDF usando ReportLab.
"""
import os
from datetime import datetime
from typing import Dict, List, Tuple
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white, red, blue, Color

from extrator import DadosProjeto
from topologia import NoRede, ArestaRede, construir_grafo

# Cores RGE
COR_FUNDO = white
COR_BORDA = black
COR_MT_EXISTENTE = black       # Rede MT existente - preta
COR_MT_NOVA = HexColor('#8B4513')  # Rede MT nova - marrom
COR_MT_RECOND = blue           # Recondutorada - azul
COR_BT_EXISTENTE = black
COR_BT_NOVA = HexColor('#8B4513')
COR_TRABALHO = red             # Área de trabalho - vermelho pontilhado
COR_HEADER_BG = HexColor('#D3D3D3')
COR_TABELA_LINHA_PAR = HexColor('#90EE90')  # verde claro
COR_TABELA_TITULO = HexColor('#228B22')
COR_EQUIPAMENTO_NOVO = HexColor('#8B4513')  # marrom para novo


VIABILIDADE_PERGUNTAS = [
    "Foi realizada a avaliação do TIPO DE SOLO para permitir executar este Obra ?",
    "Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos, se estes "
    "apresentam as condições de operação para realizar as Manobras?",
    "Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor "
    "nos casos de trabalhos de equipes de Linha Viva (Solicitação /DIRA) ?",
    "Caso seja necessário uma PREPARAÇÃO para execução da Obra, ela já foi realizada?",
    "Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?",
    "Se a execução afetar o CLIENTE, ele concorda com a intervenção?",
    "O MATERIAL para esta obra está disponível?",
    "O Tempo para execução está adequado e evita possibilidades de ATRASOS na execução "
    "ou no deslocamento para a obra?",
    "Está previsto outro DOCUMENTO RESERVA para esta obra, que será cancelado posteriormente?",
    "Este documento já foi CANCELADO ou é uma Reprogramação?",
]


def gerar_croqui_pdf(dados: DadosProjeto, caminho_saida: str):
    """Gera o PDF do croqui."""
    nos, arestas = construir_grafo(dados)

    # Página A4 paisagem
    W, H = landscape(A4)
    c = canvas.Canvas(caminho_saida, pagesize=(W, H))

    _desenhar_pagina(c, W, H, dados, nos, arestas)

    c.save()
    print(f"Croqui gerado: {caminho_saida}")


def _desenhar_pagina(c: canvas.Canvas, W: float, H: float,
                      dados: DadosProjeto, nos: Dict[str, NoRede],
                      arestas: List[ArestaRede]):
    MARGEM = 0.5 * cm

    # === CABEÇALHO ===
    _desenhar_cabecalho(c, W, H, MARGEM, dados)

    # === ÁREA DE DESENHO ===
    header_h = 2.2 * cm
    tabela_h = 7.2 * cm
    area_y = tabela_h + MARGEM
    area_h = H - header_h - tabela_h - 2 * MARGEM
    area_x = MARGEM
    area_w = W - 2 * MARGEM

    _desenhar_rede(c, area_x, area_y, area_w, area_h, dados, nos, arestas)

    # === TABELA VIABILIDADE ===
    _desenhar_tabela_viabilidade(c, W, H, MARGEM)

    # === BORDA GERAL ===
    c.setStrokeColor(black)
    c.setLineWidth(1.5)
    c.rect(MARGEM, MARGEM, W - 2*MARGEM, H - 2*MARGEM)


def _desenhar_cabecalho(c: canvas.Canvas, W: float, H: float, MARGEM: float,
                         dados: DadosProjeto):
    header_h = 2.2 * cm
    header_y = H - MARGEM - header_h

    # Fundo cinza claro
    c.setFillColor(COR_HEADER_BG)
    c.rect(MARGEM, header_y, W - 2*MARGEM, header_h, fill=1, stroke=1)

    # Logo RGE (texto simulado)
    c.setFillColor(HexColor('#006400'))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGEM + 0.3*cm, header_y + 1.5*cm, "RGE")
    c.setFont("Helvetica", 7)
    c.drawString(MARGEM + 0.3*cm, header_y + 1.1*cm, "RioGrandeEnergia")

    # Linha separadora logo
    c.setStrokeColor(black)
    c.setLineWidth(0.5)
    c.line(MARGEM + 2.8*cm, header_y, MARGEM + 2.8*cm, header_y + header_h)
    c.line(MARGEM + 2.8*cm, header_y + header_h * 0.5,
           W - MARGEM - 3*cm, header_y + header_h * 0.5)

    # Título "Croqui" centralizado
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W/2, H - MARGEM - 0.9*cm, "Croqui")

    # Campos do cabeçalho
    campos = [
        ("Departamento:", dados.departamento, MARGEM + 3*cm, header_y + 1.6*cm),
        ("Município:", dados.municipio,       MARGEM + 3*cm, header_y + 0.9*cm),
        ("Equipamento :", dados.equipamento_principal, W - MARGEM - 8*cm, header_y + 0.9*cm),
        ("Data do Levantamento:", dados.data, MARGEM + 3*cm, header_y + 0.3*cm),
        ("Levantamento de campo realizado por:", "", W/2, header_y + 0.3*cm),
    ]

    c.setFont("Helvetica-Bold", 7)
    for label, valor, x, y in campos:
        c.setFillColor(black)
        c.drawString(x, y, label)
        c.setFont("Helvetica", 7)
        c.drawString(x + c.stringWidth(label, "Helvetica-Bold", 7) + 3, y, valor)
        c.setFont("Helvetica-Bold", 7)

    # Linha inferior do cabeçalho
    c.setLineWidth(1.5)
    c.line(MARGEM, header_y, W - MARGEM, header_y)


def _desenhar_rede(c: canvas.Canvas, ax: float, ay: float, aw: float, ah: float,
                   dados: DadosProjeto, nos: Dict[str, NoRede], arestas: List[ArestaRede]):
    """Desenha a topologia da rede na área designada."""
    # Se não há topologia extraída, desenha lista de equipamentos
    if not nos or (len(nos) <= 1 and not arestas):
        _desenhar_lista_equipamentos(c, ax, ay, aw, ah, dados)
        return

    # Calcula escala: mapeia coordenadas lógicas para área de desenho
    PADDING = 1.5 * cm
    xs = [n.x for n in nos.values()]
    ys = [n.y for n in nos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    rng_x = max_x - min_x or 1
    rng_y = max_y - min_y or 1
    escala = min(
        (aw - 2*PADDING) / rng_x,
        (ah - 2*PADDING) / rng_y
    )

    def para_pdf(lx, ly):
        px = ax + PADDING + (lx - min_x) * escala
        py = ay + PADDING + (ly - min_y) * escala
        return px, py

    # Detecta área de trabalho (postes com ações de instalação)
    postes_trabalho = set()
    for poste in dados.postes:
        if '+' in poste.acoes or poste.novo:
            postes_trabalho.add(poste.id)

    # Desenha área de trabalho (caixa vermelha pontilhada)
    if postes_trabalho:
        _desenhar_area_trabalho(c, nos, postes_trabalho, para_pdf, PADDING)

    # Desenha arestas
    for aresta in arestas:
        if aresta.origem not in nos or aresta.destino not in nos:
            continue
        ox, oy = para_pdf(nos[aresta.origem].x, nos[aresta.origem].y)
        dx, dy = para_pdf(nos[aresta.destino].x, nos[aresta.destino].y)
        _desenhar_aresta(c, ox, oy, dx, dy, aresta)

    # Desenha nós
    for no in nos.values():
        px, py = para_pdf(no.x, no.y)
        _desenhar_no(c, px, py, no)


def _desenhar_area_trabalho(c, nos, postes_trabalho, para_pdf, PADDING):
    """Desenha caixa vermelha pontilhada ao redor da área de trabalho."""
    xs = [nos[p].x for p in postes_trabalho if p in nos]
    ys = [nos[p].y for p in postes_trabalho if p in nos]
    if not xs:
        return
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    p1 = para_pdf(min_x - 0.5, min_y - 0.5)
    p2 = para_pdf(max_x + 0.5, max_y + 0.5)
    bx = p1[0]
    by = p1[1]
    bw = p2[0] - p1[0]
    bh = p2[1] - p1[1]
    c.setStrokeColor(red)
    c.setLineWidth(1.0)
    c.setDash([4, 3])
    c.rect(bx, by, bw, bh, fill=0)
    c.setDash([])
    c.setFont("Helvetica", 6)
    c.setFillColor(red)
    c.drawString(bx + 2, by + bh + 2, "Área de trabalho")
    c.setFillColor(black)
    c.setStrokeColor(black)


def _desenhar_aresta(c, ox, oy, dx, dy, aresta: ArestaRede):
    """Desenha uma aresta (vão) entre dois postes."""
    if aresta.novo or aresta.cabo and ('+' in aresta.cabo):
        cor = COR_MT_NOVA if aresta.tipo == "AT" else COR_BT_NOVA
    else:
        cor = COR_MT_EXISTENTE if aresta.tipo == "AT" else COR_BT_EXISTENTE

    c.setStrokeColor(cor)
    c.setLineWidth(1.2)

    if aresta.tipo == "BT":
        c.setDash([5, 3])
    else:
        c.setDash([])

    c.line(ox, oy, dx, dy)
    c.setDash([])
    c.setStrokeColor(black)

    # Label AT/BT no meio do vão
    mid_x = (ox + dx) / 2
    mid_y = (oy + dy) / 2 + 3
    c.setFont("Helvetica", 5.5)
    c.setFillColor(cor)
    c.drawCentredString(mid_x, mid_y, aresta.tipo)
    c.setFillColor(black)


def _desenhar_no(c, px, py, no: NoRede):
    """Desenha um nó (poste, transformador, chave, etc.)."""
    R = 4  # raio do círculo de poste

    if no.tipo == "transformador":
        _desenhar_transformador(c, px, py, no)
    elif no.tipo in ("chave", "religador"):
        _desenhar_chave(c, px, py, no)
    elif no.remover:
        # Poste a remover: círculo com X
        c.setStrokeColor(red)
        c.setFillColor(white)
        c.circle(px, py, R, fill=1, stroke=1)
        c.setLineWidth(0.8)
        c.line(px - R*0.7, py - R*0.7, px + R*0.7, py + R*0.7)
        c.line(px - R*0.7, py + R*0.7, px + R*0.7, py - R*0.7)
        c.setStrokeColor(black)
    elif no.novo:
        # Poste novo: triângulo preenchido
        _desenhar_triangulo_poste(c, px, py, COR_EQUIPAMENTO_NOVO)
    else:
        # Poste existente: círculo com ponto central
        c.setStrokeColor(black)
        c.setFillColor(white)
        c.circle(px, py, R, fill=1, stroke=1)
        c.setFillColor(black)
        c.circle(px, py, 1.2, fill=1, stroke=0)

    # Label do ID
    if no.label:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(black)
        c.drawCentredString(px, py - R - 7, no.label)
        if no.kva:
            c.drawCentredString(px, py - R - 13, no.kva)
    elif no.id.startswith('P') and no.id[1:].isdigit():
        # Não exibe label de poste no croqui final (estilo RGE não mostra P1, P2...)
        pass


def _desenhar_transformador(c, px, py, no: NoRede):
    """Desenha símbolo de transformador (triângulo invertido)."""
    h = 10
    cor = COR_EQUIPAMENTO_NOVO if no.novo else black

    c.setStrokeColor(cor)
    c.setFillColor(white)
    c.setLineWidth(1.2)

    # Triângulo apontando para baixo
    path = c.beginPath()
    path.moveTo(px - 7, py + h/2)
    path.lineTo(px + 7, py + h/2)
    path.lineTo(px, py - h/2)
    path.close()
    c.drawPath(path, fill=1, stroke=1)

    # Aterramento (linhas abaixo)
    c.setLineWidth(0.8)
    c.line(px, py - h/2, px, py - h/2 - 4)
    c.line(px - 4, py - h/2 - 4, px + 4, py - h/2 - 4)
    c.line(px - 2.5, py - h/2 - 6, px + 2.5, py - h/2 - 6)
    c.line(px - 1, py - h/2 - 8, px + 1, py - h/2 - 8)

    c.setStrokeColor(black)

    # Label
    if no.label:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(cor)
        c.drawCentredString(px, py - h/2 - 13, no.label)
        if no.kva:
            c.drawCentredString(px, py - h/2 - 19, no.kva)
        c.setFillColor(black)


def _desenhar_chave(c, px, py, no: NoRede):
    """Desenha símbolo de chave/religador (quadrado com X)."""
    S = 6
    c.setStrokeColor(black)
    c.setFillColor(white)
    c.setLineWidth(1.2)
    c.rect(px - S, py - S, 2*S, 2*S, fill=1, stroke=1)

    if no.tipo == "religador":
        # Religador: quadrado com triângulo interno
        path = c.beginPath()
        path.moveTo(px - S*0.5, py - S*0.5)
        path.lineTo(px + S*0.5, py - S*0.5)
        path.lineTo(px, py + S*0.5)
        path.close()
        c.setFillColor(black)
        c.drawPath(path, fill=1, stroke=0)
    else:
        # Chave: X dentro do quadrado
        c.setLineWidth(0.8)
        c.line(px - S*0.7, py - S*0.7, px + S*0.7, py + S*0.7)
        c.line(px - S*0.7, py + S*0.7, px + S*0.7, py - S*0.7)

    # Label
    if no.label:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(black)
        c.drawCentredString(px, py - S - 7, no.label)


def _desenhar_triangulo_poste(c, px, py, cor):
    """Desenha triângulo para poste novo."""
    h = 10
    c.setStrokeColor(cor)
    c.setFillColor(cor)
    c.setLineWidth(1.0)
    path = c.beginPath()
    path.moveTo(px, py + h * 0.6)
    path.lineTo(px - 6, py - h * 0.4)
    path.lineTo(px + 6, py - h * 0.4)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    c.setFillColor(black)
    c.setStrokeColor(black)


def _desenhar_lista_equipamentos(c, ax, ay, aw, ah, dados: DadosProjeto):
    """
    Fallback: quando a topologia não foi extraída, exibe lista dos
    equipamentos identificados no estilo do croqui (IDs em cadeia linear).
    """
    RAIO = 5
    ESPAC_X = 2.2 * cm
    ESPAC_Y = 1.8 * cm

    # Todos os IDs únicos de equipamentos
    ids = []
    trs = {tr.numero: tr for tr in dados.transformadores}

    for eid in dados.equipamentos_ids:
        if eid not in [i[0] for i in ids]:
            ids.append((eid, eid in trs))

    if not ids:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor('#555555'))
        c.drawCentredString(ax + aw * 0.4, ay + ah * 0.5,
                            "Topologia não extraída automaticamente.")
        c.drawCentredString(ax + aw * 0.4, ay + ah * 0.5 - 14,
                            "Verifique os dados e desenhe o croqui manualmente no Excel.")
        c.setFillColor(black)
        return

    # Desenha cadeia horizontal de equipamentos
    n_por_linha = max(1, int((aw * 0.75) / ESPAC_X))
    centro_y = ay + ah * 0.6

    for i, (eid, is_tr) in enumerate(ids):
        col = i % n_por_linha
        lin = i // n_por_linha
        px = ax + 2*cm + col * ESPAC_X
        py = centro_y - lin * ESPAC_Y

        # Linha conectora
        if col > 0:
            prev_px = ax + 2*cm + (col-1) * ESPAC_X
            c.setStrokeColor(black)
            c.setLineWidth(1.0)
            c.setDash([])
            c.line(prev_px + RAIO, py, px - RAIO, py)
        elif lin > 0:
            # Volta de linha
            prev_px = ax + 2*cm + (n_por_linha - 1) * ESPAC_X
            c.line(prev_px, py + ESPAC_Y, prev_px, py + ESPAC_Y - ESPAC_Y*0.3)
            c.line(prev_px, py + ESPAC_Y*0.7, ax + 2*cm, py + ESPAC_Y*0.7)
            c.line(ax + 2*cm, py + ESPAC_Y*0.7, ax + 2*cm, py)

        if is_tr:
            tr = trs[eid]
            # Triângulo de transformador
            h = 10
            c.setStrokeColor(black)
            c.setFillColor(white)
            c.setLineWidth(1.2)
            path = c.beginPath()
            path.moveTo(px - 7, py + h/2)
            path.lineTo(px + 7, py + h/2)
            path.lineTo(px, py - h/2)
            path.close()
            c.drawPath(path, fill=1, stroke=1)
            # Aterramento
            c.line(px, py - h/2, px, py - h/2 - 5)
            c.line(px - 4, py - h/2 - 5, px + 4, py - h/2 - 5)
            c.line(px - 2.5, py - h/2 - 7, px + 2.5, py - h/2 - 7)
            # Label
            c.setFont("Helvetica", 5.5)
            c.drawCentredString(px, py - h/2 - 14, eid)
            c.drawCentredString(px, py - h/2 - 20, f"{tr.kva:.0f}kVA")
            # Tipo BT/AT
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(px, py + h/2 + 4, "BT")
        else:
            # Círculo de poste/equipamento
            c.setStrokeColor(black)
            c.setFillColor(white)
            c.circle(px, py, RAIO, fill=1, stroke=1)
            c.setFillColor(black)
            c.circle(px, py, 1.5, fill=1, stroke=0)
            # Label
            c.setFont("Helvetica", 5.5)
            c.drawCentredString(px, py - RAIO - 7, eid)

    # Label de área de trabalho
    eq_p = dados.equipamento_principal
    if eq_p:
        # Destaca o equipamento principal com caixa vermelha
        num_eq = eq_p.split()[-1] if ' ' in eq_p else eq_p
        for i, (eid, is_tr) in enumerate(ids):
            if eid == num_eq:
                col = i % n_por_linha
                lin = i // n_por_linha
                px = ax + 2*cm + col * ESPAC_X
                py = centro_y - lin * ESPAC_Y
                c.setStrokeColor(red)
                c.setLineWidth(0.8)
                c.setDash([3, 2])
                c.rect(px - 15, py - 20, 30, 35, fill=0)
                c.setDash([])
                c.setStrokeColor(black)
                break

    c.setFillColor(black)


def _desenhar_tabela_viabilidade(c: canvas.Canvas, W: float, H: float, MARGEM: float):
    """Desenha a tabela de Avaliação de Viabilidade na parte inferior."""
    TABELA_H = 7.0 * cm
    tabela_y = MARGEM
    tabela_x = MARGEM
    tabela_w = W - 2*MARGEM

    # Linha de título
    titulo_h = 0.55 * cm
    c.setFillColor(COR_TABELA_TITULO)
    c.rect(tabela_x, tabela_y + TABELA_H - titulo_h, tabela_w, titulo_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        tabela_x + tabela_w * 0.35,
        tabela_y + TABELA_H - titulo_h + 0.15*cm,
        "Avaliação de Viabilidade"
    )
    c.drawString(
        tabela_x + tabela_w * 0.65,
        tabela_y + TABELA_H - titulo_h + 0.15*cm,
        "* Preenchimento obrigatório com Sim, Não ou Não Avaliado"
    )

    # "Viabilidade: 100,0%"
    viab_x = tabela_x + tabela_w * 0.88
    c.setFillColor(COR_TABELA_TITULO)
    c.rect(viab_x, tabela_y + TABELA_H - titulo_h, tabela_w * 0.12, titulo_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(viab_x + 3, tabela_y + TABELA_H - titulo_h + 0.15*cm, "Viabilidade:")
    c.setFillColor(HexColor('#FFD700'))
    c.drawRightString(tabela_x + tabela_w - 3, tabela_y + TABELA_H - titulo_h + 0.15*cm, "100,0%")

    # Linhas da tabela
    linha_h = (TABELA_H - titulo_h) / len(VIABILIDADE_PERGUNTAS)
    respostas = ["Sim"] * 9 + ["Não"]

    for i, (pergunta, resposta) in enumerate(zip(VIABILIDADE_PERGUNTAS, respostas)):
        ly = tabela_y + TABELA_H - titulo_h - (i + 1) * linha_h

        # Fundo alternado
        cor_fundo = COR_TABELA_LINHA_PAR if i % 2 == 0 else HexColor('#C8E6C9')
        c.setFillColor(cor_fundo)
        c.rect(tabela_x, ly, tabela_w * 0.88, linha_h, fill=1, stroke=0)

        # Borda
        c.setStrokeColor(HexColor('#006400'))
        c.setLineWidth(0.3)
        c.rect(tabela_x, ly, tabela_w * 0.88, linha_h, fill=0, stroke=1)

        # Texto da pergunta
        c.setFillColor(black)
        c.setFont("Helvetica", 6)
        texto = pergunta[:100]
        c.drawString(tabela_x + 3, ly + linha_h * 0.25, texto)

        # Resposta
        resp_x = tabela_x + tabela_w * 0.88
        resp_w = tabela_w * 0.12
        cor_resp = HexColor('#006400') if resposta == "Sim" else COR_TABELA_TITULO
        c.setFillColor(cor_resp)
        c.rect(resp_x, ly, resp_w, linha_h, fill=1, stroke=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(resp_x + resp_w/2, ly + linha_h * 0.25, resposta)

    c.setFillColor(black)
    c.setStrokeColor(black)
