"""
gerador_excel.py - Preenche o template Excel (.xls) com os dados do projeto.
Copia o template existente e atualiza os campos de cabeçalho.
"""
import os
import shutil
from datetime import datetime
import xlrd
from xlutils.copy import copy as xl_copy
import xlwt

from extrator import DadosProjeto

# Caminho do template base (usa o Projeto 1 como referência)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
TEMPLATE_FILE = os.path.join(TEMPLATE_DIR, "croqui_template.xls")


def gerar_croqui_excel(dados: DadosProjeto, caminho_saida: str,
                       template_path: str = None):
    """
    Gera o Excel do croqui preenchendo o template com os dados do projeto.
    Se template_path não for fornecido, usa o template padrão.
    """
    if template_path is None:
        template_path = TEMPLATE_FILE

    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f"Template não encontrado: {template_path}\n"
            f"Copie um dos arquivos .xls de exemplo para {template_path}"
        )

    # Abre o template e cria cópia editável
    wb_leitura = xlrd.open_workbook(template_path, formatting_info=True)
    wb_escrita = xl_copy(wb_leitura)

    ws = wb_escrita.get_sheet(0)  # Aba "Croqui v1"

    # Estilos
    estilo_valor = xlwt.XFStyle()
    fonte = xlwt.Font()
    fonte.name = 'Arial'
    fonte.height = 200  # 10pt
    estilo_valor.font = fonte

    estilo_bold = xlwt.XFStyle()
    fonte_bold = xlwt.Font()
    fonte_bold.name = 'Arial'
    fonte_bold.height = 200
    fonte_bold.bold = True
    estilo_bold.font = fonte_bold

    # ===== LINHA 4 (índice 4): Departamento, Município, Equipamento =====
    # col1=Departamento (label), col8=valor, col15=Município (label),
    # col26=valor, col33=Equipamento (label), col41=valor
    ws.write(4, 8, dados.departamento, estilo_valor)
    ws.write(4, 26, dados.municipio, estilo_valor)
    ws.write(4, 41, dados.equipamento_principal, estilo_bold)

    # ===== LINHA 5 (índice 5): Data e Levantador =====
    # col8=data (número Excel), col33=nome levantador
    if dados.data:
        try:
            d, m, a = dados.data.split('/')
            from datetime import date
            dt = date(int(a), int(m), int(d))
            # Converte para número serial Excel (dias desde 01/01/1900)
            excel_date = (dt - date(1899, 12, 30)).days
            ws.write(5, 8, excel_date, estilo_valor)
        except Exception:
            ws.write(5, 8, dados.data, estilo_valor)

    # ===== EQUIPAMENTOS NA ÁREA DE DESENHO =====
    # Escreve lista de equipamentos na área de anotações (linhas 7-27)
    linha_eq = 7
    equipamentos_texto = _formatar_equipamentos(dados)
    for i, linha in enumerate(equipamentos_texto.split('\n')):
        if linha_eq + i >= 27:
            break
        ws.write(linha_eq + i, 0, linha, estilo_valor)

    # ===== RESPOSTAS DA VIABILIDADE (linhas 32-41) =====
    # Todas Sim exceto última (Não)
    respostas = ["Sim"] * 9 + ["Não"]
    for i, resp in enumerate(respostas):
        ws.write(32 + i, 42, resp, estilo_valor)

    # Salva
    wb_escrita.save(caminho_saida)
    print(f"Excel gerado: {caminho_saida}")


def _formatar_equipamentos(dados: DadosProjeto) -> str:
    """Formata lista de equipamentos para inserir no Excel."""
    linhas = []

    if dados.equipamento_principal:
        linhas.append(f"Equipamento: {dados.equipamento_principal}")

    for tr in dados.transformadores:
        linhas.append(f"{tr.numero}")
        linhas.append(f"{tr.kva:.2f}kVA")

    for eid in dados.equipamentos_ids:
        if eid not in [t.numero for t in dados.transformadores]:
            linhas.append(eid)

    if dados.obra:
        linhas.append(f"Obra: {dados.obra[:40]}")

    return '\n'.join(linhas)


def copiar_template_de_exemplo(caminho_exemplo: str):
    """Copia um arquivo .xls de exemplo como template."""
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    shutil.copy2(caminho_exemplo, TEMPLATE_FILE)
    print(f"Template configurado: {TEMPLATE_FILE}")
