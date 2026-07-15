"""
extrator.py - Extrai dados de projetos elétricos CPFL/RGE (PDF CAD).
Usa extração posicional pois PDFs CAD têm texto em ordem aleatória.
"""
import re
import sys
import pdfplumber
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Transformador:
    numero: str
    kva: float
    tensao: str = "23.1-380"
    novo: bool = False


@dataclass
class Poste:
    id: str
    tipo: str = ""
    novo: bool = False
    remover: bool = False
    tem_transformador: bool = False
    tem_chave: bool = False
    equipamento_id: str = ""
    acoes: str = ""


@dataclass
class Vao:
    origem: str
    destino: str
    cabo: str = ""
    comprimento: float = 0.0
    novo: bool = False


@dataclass
class DadosProjeto:
    nota: str = ""
    municipio: str = ""
    departamento: str = "SERRA"
    obra: str = ""
    endereco: str = ""
    cliente: str = ""
    projetista: str = ""
    data: str = ""
    equipamento_principal: str = ""
    transformadores: List[Transformador] = field(default_factory=list)
    postes: List[Poste] = field(default_factory=list)
    vaos: List[Vao] = field(default_factory=list)
    equipamentos_ids: List[str] = field(default_factory=list)
    area_trabalho: List[str] = field(default_factory=list)


def extrair_projeto(caminho_pdf: str) -> DadosProjeto:
    dados = DadosProjeto()
    palavras_por_pagina = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False
            )
            palavras_por_pagina.append((page, words))

    # Reconstrói texto em ordem de leitura (top→bottom, left→right)
    texto_ordenado = _reconstruir_texto(palavras_por_pagina)

    # Texto simples para buscas rápidas
    texto_simples = " ".join(texto_ordenado)

    _extrair_cabecalho(texto_simples, texto_ordenado, dados)
    _extrair_transformadores(texto_simples, dados)
    _extrair_postes_vaos(texto_ordenado, dados)
    _extrair_equipamento_principal(texto_simples, palavras_por_pagina, dados)
    _enriquecer_ids(texto_simples, dados)

    return dados


def _reconstruir_texto(palavras_por_pagina) -> List[str]:
    """
    Reconstrói linhas de texto ordenando palavras por posição (y desc, x asc).
    Agrupa palavras na mesma linha (tolerância vertical = 5pt).
    PDFs CAD frequentemente têm dígitos espaçados: "6 8 9 7 2 6" → "689726".
    """
    linhas = []

    for page, words in palavras_por_pagina:
        if not words:
            continue

        # Ordena por y (topo da página primeiro = maior y no sistema PDF)
        words_sorted = sorted(words, key=lambda w: (-w['top'], w['x0']))

        linha_atual = []
        y_atual = None
        TOL_Y = 5  # tolerância vertical para mesma linha

        for w in words_sorted:
            if y_atual is None or abs(w['top'] - y_atual) > TOL_Y:
                if linha_atual:
                    linha = ' '.join(linha_atual)
                    linha = _colapsar_digitos_espacados(linha)
                    linhas.append(linha)
                linha_atual = [w['text']]
                y_atual = w['top']
            else:
                linha_atual.append(w['text'])

        if linha_atual:
            linha = ' '.join(linha_atual)
            linha = _colapsar_digitos_espacados(linha)
            linhas.append(linha)

    return linhas


def _colapsar_digitos_espacados(linha: str) -> str:
    """
    Colapsa sequências de dígitos/pontos separados por espaço simples.
    Ex: "3 6 8 9 7 2 6 75 .0 0 kVA" → "689726 75.00 kVA"
    Apenas colapsa tokens de 1-2 chars que são dígitos ou pontos.
    """
    tokens = linha.split(' ')
    resultado = []
    grupo = []

    def eh_digito_ponto(t):
        return len(t) <= 2 and re.match(r'^[\d.]+$', t)

    for t in tokens:
        if eh_digito_ponto(t):
            grupo.append(t)
        else:
            if grupo:
                # Junta o grupo e remove pontos duplicados
                joined = ''.join(grupo)
                # Remove caracteres não numéricos que possam ter sido misturados
                # Mantém ponto decimal se houver
                resultado.append(joined)
                grupo = []
            resultado.append(t)

    if grupo:
        resultado.append(''.join(grupo))

    return ' '.join(resultado)


def _extrair_cabecalho(texto: str, linhas: List[str], dados: DadosProjeto):
    """Extrai dados do bloco de título (rodapé do projeto)."""
    # Nota fiscal/obra
    m = re.search(r'Nota[:\s]+(\d{9,15})', texto)
    if m:
        dados.nota = m.group(1)

    # Município - busca próximo de "Município:" ou "Municipio:"
    m = re.search(r'Munic[íi]pio[:\s]+([A-Za-záéíóúãõâêôçÁÉÍÓÚÃÕÂÊÔÇ\s]+?)(?:\s{2,}|\n|Folha|Nota|Escala|AL:)', texto)
    if m:
        dados.municipio = m.group(1).strip()
    else:
        # Busca pelo padrão "AL: VAC25" → município Vacaria
        m = re.search(r'AL:\s*([A-Z]{3})', texto)
        if m:
            cod = m.group(1)
            mapa_al = {'VAC': 'Vacaria', 'APR': 'Ipê', 'BEN': 'Bento Gonçalves',
                       'CAX': 'Caxias do Sul'}
            dados.municipio = mapa_al.get(cod[:3], dados.municipio)

    # Município direto no texto
    if not dados.municipio:
        for linha in linhas:
            if 'Munic' in linha and ':' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    dados.municipio = partes[1].strip().split()[0]
                    break

    # Obra
    m = re.search(r'Obra[:\s]+(.+?)(?:\n|Endere)', texto, re.IGNORECASE)
    if m:
        dados.obra = m.group(1).strip()[:80]

    # Endereço
    m = re.search(r'Endere[çc]o[:\s]+(.+?)(?:\n|Respons)', texto, re.IGNORECASE)
    if m:
        dados.endereco = m.group(1).strip()[:80]

    # Cliente
    m = re.search(r'Cliente[:\s]+(.+?)(?:\n|Projet|Obra)', texto, re.IGNORECASE)
    if m:
        dados.cliente = m.group(1).strip()[:60]

    # Projetista
    m = re.search(r'Projetista[:\s]+(.+?)(?:\n|Data)', texto, re.IGNORECASE)
    if m:
        dados.projetista = m.group(1).strip()[:40]

    # Data
    m = re.search(r'Data[:\s]+(\d{2}/\d{2}/\d{4})', texto)
    if m:
        dados.data = m.group(1)

    # Departamento (Gerência)
    m = re.search(r'Gerência[^:]*de\s+Rede[^:]*:\s*(\w+)', texto, re.IGNORECASE)
    if m:
        dados.departamento = m.group(1).strip()
    else:
        # Tenta "AL: VAC25" → SERRA, "AL: APR12" → SERRA, etc.
        m = re.search(r'AL:\s*([A-Z]{3})', texto)
        if m:
            dados.departamento = "SERRA"  # padrão RGE Serra
        else:
            # Detecta "SERRA", "SUL", etc. no texto
            m_dept = re.search(r'\b(SERRA|SUL DISTRIBUIDORA|LESTE|OESTE|NORTE|CENTRO)\b', texto)
            if m_dept:
                dados.departamento = m_dept.group(1).split()[0]


def _extrair_transformadores(texto: str, dados: DadosProjeto):
    """Extrai transformadores pelo padrão: NUMERO XX.XX kVA TENSAO."""
    # Padrão principal: 689726 75.00 kVA 23.1-380
    padrao = re.compile(r'\b(\d{6,8})\s+([\d.]+)\s*kVA\s*([\d.\-]*)', re.IGNORECASE)
    vistos = set()

    for m in padrao.finditer(texto):
        num = m.group(1)
        # Descarta números que não são IDs de equipamento
        if len(num) > 8 or num.startswith('30000'):
            continue
        # Remove prefixo de fase de cabos colados: "3A1/0" → "3" prefixado ao número
        # Ex: "3689726" vem de "3 6 8 9 7 2 6" onde o "3" é do cabo "3S3/0"
        if len(num) == 7 and num[0] in '13':
            candidato = num[1:]
            ctx_antes = texto[max(0, m.start()-15):m.start()]
            if re.search(r'\b3[SAECsaec]', ctx_antes) or re.search(r'\d\s+\d\s+\d', ctx_antes):
                num = candidato
        if num in vistos:
            continue
        if num in vistos:
            continue
        try:
            kva = float(m.group(2))
        except ValueError:
            continue
        if kva < 1 or kva > 10000:  # sanidade
            continue
        vistos.add(num)
        tensao = m.group(3).strip() if m.group(3) else "23.1-380"
        tr = Transformador(numero=num, kva=kva, tensao=tensao or "23.1-380")
        dados.transformadores.append(tr)
        if num not in dados.equipamentos_ids:
            dados.equipamentos_ids.append(num)

    # Padrão para texto "REFERENCIA 689726" + "75.00 kVA" em linhas próximas
    # ou "689726\n75.00 kVA"
    padrao2 = re.compile(
        r'(?:REFERENCIA|REFERÊNCIA)?\s*(\d{6,8})\b[^\n]{0,30}\n?[^\n]{0,15}'
        r'([\d.]+)\s*kVA',
        re.IGNORECASE
    )
    for m in padrao2.finditer(texto):
        num = m.group(1)
        if num not in vistos and not num.startswith('30000'):
            try:
                kva = float(m.group(2))
                if 1 <= kva <= 10000:
                    vistos.add(num)
                    tr = Transformador(numero=num, kva=kva)
                    dados.transformadores.append(tr)
                    if num not in dados.equipamentos_ids:
                        dados.equipamentos_ids.append(num)
            except ValueError:
                pass

    # Busca por números no texto com contexto "kVA" próximo (tolerância de 80 chars)
    if not dados.transformadores:
        _extrair_trafos_por_contexto(texto, vistos, dados)


def _extrair_trafos_por_contexto(texto: str, vistos: set, dados: DadosProjeto):
    """Extrai transformadores buscando kVA e número próximo."""
    for m_kva in re.finditer(r'([\d.]+)\s*kVA', texto, re.IGNORECASE):
        try:
            kva = float(m_kva.group(1))
        except ValueError:
            continue
        if not (1 <= kva <= 10000):
            continue

        # Busca número de 6-7 dígitos nos 100 chars ao redor
        vizinho = texto[max(0, m_kva.start()-80):m_kva.end()+20]
        nums = re.findall(r'\b(\d{6,7})\b', vizinho)
        for num in nums:
            if num not in vistos and not num.startswith('30000'):
                vistos.add(num)
                tr = Transformador(numero=num, kva=kva)
                dados.transformadores.append(tr)
                if num not in dados.equipamentos_ids:
                    dados.equipamentos_ids.append(num)
                break


def _extrair_postes_vaos(linhas: List[str], dados: DadosProjeto):
    """Extrai postes e vãos das anotações do projeto."""
    # Junta linhas próximas para reconstruir anotações de postes/vãos
    texto_bloco = '\n'.join(linhas)

    # Postes: ( P1 ) ou (P1)
    padrao_poste = re.compile(r'\(\s*(P\d+)\s*\)\s*([^\n(]{5,100})', re.MULTILINE)
    vistos_p = set()

    for m in padrao_poste.finditer(texto_bloco):
        pid = m.group(1)
        if pid in vistos_p:
            continue
        vistos_p.add(pid)
        conteudo = m.group(2).strip()
        poste = _criar_poste(pid, conteudo)
        dados.postes.append(poste)

    # Vãos: ( V1-2 ) ou (V1-3)
    padrao_vao = re.compile(
        r'\(\s*V(\d+)-(\d+)\s*\)\s*([\w/()]*)\s*([\d.]+)m',
        re.MULTILINE
    )
    vistos_v = set()

    for m in padrao_vao.finditer(texto_bloco):
        key = f"V{m.group(1)}-{m.group(2)}"
        if key in vistos_v:
            continue
        vistos_v.add(key)
        vao = Vao(
            origem=f"P{m.group(1)}",
            destino=f"P{m.group(2)}",
            cabo=m.group(3).strip(),
            comprimento=float(m.group(4))
        )
        dados.vaos.append(vao)

    # Vãos com comprimento em MTS (alternativo)
    padrao_mts = re.compile(
        r'V(\d+)-(\d+)\s+([\d.]+)\s*MTS',
        re.MULTILINE | re.IGNORECASE
    )
    for m in padrao_mts.finditer(texto_bloco):
        key = f"V{m.group(1)}-{m.group(2)}"
        if key not in vistos_v:
            vistos_v.add(key)
            vao = Vao(
                origem=f"P{m.group(1)}",
                destino=f"P{m.group(2)}",
                comprimento=float(m.group(3))
            )
            dados.vaos.append(vao)

    # Se poucos postes/vãos extraídos, tenta padrão alternativo sem parênteses
    if len(dados.postes) < 2:
        _extrair_postes_alternativo(texto_bloco, vistos_p, dados)


def _criar_poste(pid: str, conteudo: str) -> Poste:
    poste = Poste(id=pid)

    # Novo (tem '+' no início ou depois de '-')
    if re.search(r'^\+\s*\d|;\s*\+|^[^-]*\+\s*\d', conteudo):
        poste.novo = True

    # Tipo de poste (primeiro token alfanumérico)
    tipo_m = re.match(r'([+-]?\s*)?(\d+[/\w]*(?:DT|AA|M)?)', conteudo.strip())
    if tipo_m:
        poste.tipo = tipo_m.group(2)

    # Transformador?
    if re.search(r'TRT|ET_TR|INSTALAR TR|REINSTALAR TR|3X\s*\dH|kVA', conteudo, re.IGNORECASE):
        poste.tem_transformador = True

    # Chave/seccionamento?
    if re.search(r'\b(CS|MS|LS)\d+[agri]|CFus|ETRSsp|ETRMsp|ETRNsp', conteudo):
        poste.tem_chave = True

    # Remover?
    if 'REMOVER POSTE' in conteudo.upper() or '- ' in conteudo[:5]:
        poste.remover = True

    # Número de equipamento na anotação
    num_m = re.search(r'\b(\d{6,8})\b', conteudo)
    if num_m:
        poste.equipamento_id = num_m.group(1)

    poste.acoes = conteudo[:100]
    return poste


def _extrair_postes_alternativo(texto: str, vistos: set, dados: DadosProjeto):
    """Tenta padrões alternativos se poucos postes foram encontrados."""
    padrao = re.compile(r'\bP(\d+)\b\s+(\d+[/\w]+)')
    for m in padrao.finditer(texto):
        pid = f"P{m.group(1)}"
        if pid not in vistos:
            vistos.add(pid)
            poste = Poste(id=pid, tipo=m.group(2))
            dados.postes.append(poste)


def _extrair_equipamento_principal(texto: str, palavras_por_pagina, dados: DadosProjeto):
    """Detecta equipamento principal pelo Plano de Execução."""
    # Padrão: tabela do plano de execução
    m = re.search(
        r'(?:Abrir|Fechar)[^\n]*?(?:Transformador|Religador|Seccionalizadora|'
        r'Chave)[^\n]*?(\d{6,8})',
        texto, re.IGNORECASE
    )
    if m:
        numero = m.group(1)
        # Determina tipo pelo contexto
        contexto = texto[max(0,m.start()-10):m.end()]
        if 'Transformador' in contexto:
            sigla = 'TR'
        elif 'Religador' in contexto:
            sigla = 'RL'
        elif 'Seccionalizadora' in contexto:
            sigla = 'SE'
        else:
            sigla = 'FC'
        dados.equipamento_principal = f"{sigla} {numero}"
        if numero not in dados.equipamentos_ids:
            dados.equipamentos_ids.insert(0, numero)
        return

    # Busca pelo TC - Telecontrolado (religador)
    m = re.search(r'(\d{6,7})-630\s+TC', texto)
    if m:
        dados.equipamento_principal = f"RL {m.group(1)}"
        return

    # Infere pelo tipo de obra
    obra = dados.obra.upper()
    if 'TRANSFORMADOR' in obra or 'LIGAÇÃO NOVA' in obra:
        if dados.transformadores:
            # Pega o transformer marcado como novo ou o mais recente
            dados.equipamento_principal = f"TR {dados.transformadores[0].numero}"
    elif 'FUSÍVEL' in obra or 'FUSIVELAMENTO' in obra:
        dados.equipamento_principal = "FC"
    elif 'RELIGADOR' in obra:
        dados.equipamento_principal = "RL"
    elif dados.transformadores:
        dados.equipamento_principal = f"TR {dados.transformadores[0].numero}"


def _enriquecer_ids(texto: str, dados: DadosProjeto):
    """Coleta IDs extras de equipamentos relevantes (religadores, chaves, postes)."""
    # IDs de 6-7 dígitos associados a equipamentos conhecidos
    padrao = re.compile(r'\b(\d{6,7})\b')
    vistos = set(dados.equipamentos_ids)

    for m in padrao.finditer(texto):
        num = m.group(1)
        if num in vistos:
            continue
        # Contexto próximo
        inicio = max(0, m.start() - 40)
        fim = min(len(texto), m.end() + 40)
        ctx = texto[inicio:fim]

        # Indica equipamento se há tipo de instalação próximo
        if re.search(r'\b(TR|RL|TC|Próprio|kVA|630|400)\b', ctx):
            vistos.add(num)
            dados.equipamentos_ids.append(num)
