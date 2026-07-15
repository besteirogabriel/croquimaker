"""
topologia.py - Constrói e posiciona o grafo da rede elétrica para o croqui.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from extrator import DadosProjeto


@dataclass
class NoRede:
    id: str
    x: float = 0.0
    y: float = 0.0
    tipo: str = "poste"      # poste, transformador, chave, religador, fim_rede
    novo: bool = False
    remover: bool = False
    label: str = ""
    kva: str = ""
    subtipo: str = ""        # AT, BT, AT/BT, MT/BT


@dataclass
class ArestaRede:
    origem: str
    destino: str
    tipo: str = "AT"         # AT, BT, AT/BT
    novo: bool = False
    cabo: str = ""
    comprimento: float = 0.0


def construir_grafo(dados: DadosProjeto) -> Tuple[Dict[str, NoRede], List[ArestaRede]]:
    """Constrói o grafo da rede a partir dos dados extraídos."""
    nos: Dict[str, NoRede] = {}
    arestas: List[ArestaRede] = []

    # Cria nós para postes
    for poste in dados.postes:
        no = NoRede(id=poste.id, novo=poste.novo, remover=poste.remover)
        if poste.tem_transformador:
            no.tipo = "transformador"
        elif poste.tem_chave:
            no.tipo = "chave"
        nos[poste.id] = no

    # Adiciona nós para transformadores identificados nos postes
    for tr in dados.transformadores:
        # Verifica se algum poste já está associado a esse TR
        label_tr = f"TR {tr.numero}"
        for poste in dados.postes:
            if tr.numero in poste.acoes:
                nos[poste.id].tipo = "transformador"
                nos[poste.id].label = tr.numero
                nos[poste.id].kva = f"{tr.kva:.0f}kVA"
                break

    # Cria arestas para vãos
    for vao in dados.vaos:
        # Garante que os nós existem
        if vao.origem not in nos:
            nos[vao.origem] = NoRede(id=vao.origem)
        if vao.destino not in nos:
            nos[vao.destino] = NoRede(id=vao.destino)

        # Determina tipo (AT=alta tensão/MT, BT=baixa tensão)
        tipo = _determinar_tipo_vao(vao.cabo)
        aresta = ArestaRede(
            origem=vao.origem,
            destino=vao.destino,
            tipo=tipo,
            novo=vao.novo,
            cabo=vao.cabo,
            comprimento=vao.comprimento
        )
        arestas.append(aresta)

    # Adiciona equipamentos extras como nós
    _adicionar_equipamentos_extras(dados, nos)

    # Calcula posições
    _calcular_posicoes(nos, arestas)

    return nos, arestas


def _determinar_tipo_vao(cabo: str) -> str:
    """Determina se o vão é AT, BT ou AT/BT pelo tipo de cabo."""
    if not cabo:
        return "AT"
    cabo = cabo.upper()
    # Cabos de baixa tensão
    if any(x in cabo for x in ['S04', 'S02', 'S2', 'S4', 'CAZ', 'BT']):
        return "BT"
    # Cabos múltiplos (AT+BT)
    if '/' in cabo and any(x in cabo for x in ['S', 'BT']):
        return "AT/BT"
    return "AT"


def _adicionar_equipamentos_extras(dados: DadosProjeto, nos: Dict[str, NoRede]):
    """Adiciona equipamentos identificados mas sem poste associado."""
    # Transformadores não associados a postes
    for tr in dados.transformadores:
        if tr.numero not in [n.label for n in nos.values()]:
            # Cria nó virtual para este transformador
            nid = f"TR_{tr.numero}"
            no = NoRede(
                id=nid,
                tipo="transformador",
                label=tr.numero,
                kva=f"{tr.kva:.0f}kVA"
            )
            nos[nid] = no

    # Religadores/chaves nos equipamentos_ids
    equip = dados.equipamento_principal
    if equip and equip.startswith(('RL ', 'FC ', 'FU ')):
        num = equip.split(' ')[1] if ' ' in equip else ''
        if num:
            nid = f"EQ_{num}"
            if nid not in nos:
                sigla = equip.split(' ')[0]
                tipo_map = {'RL': 'religador', 'FC': 'chave', 'FU': 'chave'}
                no = NoRede(
                    id=nid,
                    tipo=tipo_map.get(sigla, 'chave'),
                    label=num
                )
                nos[nid] = no


def _calcular_posicoes(nos: Dict[str, NoRede], arestas: List[ArestaRede]):
    """
    Layout da rede elétrica.
    Estratégia: posiciona postes em cadeia linear (horizontal), com
    derivações para baixo, seguindo a topologia da rede.
    """
    if not nos:
        return

    postes_numerados = sorted(
        [n for n in nos.values() if n.id.startswith('P') and n.id[1:].isdigit()],
        key=lambda n: int(n.id[1:])
    )

    if not postes_numerados:
        for i, no in enumerate(nos.values()):
            no.x = (i % 8) * 2.5
            no.y = -(i // 8) * 2.5
        return

    # Grafo de adjacência
    adj: Dict[str, List[str]] = {n.id: [] for n in nos.values()}
    for ar in arestas:
        if ar.origem in adj:
            adj[ar.origem].append(ar.destino)
        if ar.destino in adj:
            adj[ar.destino].append(ar.origem)

    EX = 2.5   # espaçamento horizontal
    EY = 2.5   # espaçamento vertical (derivação)

    visitados: set = set()
    fila = [(postes_numerados[0].id, 0.0, 0.0, 'H')]  # (id, x, y, direção)
    ramo_y: Dict[float, int] = {}  # quantas derivações já existem em x

    while fila:
        nid, cx, cy, direcao = fila.pop(0)
        if nid in visitados:
            continue
        visitados.add(nid)
        nos[nid].x = cx
        nos[nid].y = cy

        vizinhos = sorted(
            [v for v in adj.get(nid, []) if v not in visitados],
            key=lambda v: int(v[1:]) if v.startswith('P') and v[1:].isdigit() else 999
        )

        for i, viz in enumerate(vizinhos):
            if viz in visitados:
                continue
            if i == 0:
                # Primeiro vizinho: continua na mesma direção (horizontal)
                fila.append((viz, cx + EX, cy, 'H'))
            else:
                # Derivação: vai para baixo
                n_ramos = ramo_y.get(cx, 0)
                ramo_y[cx] = n_ramos + 1
                fila.append((viz, cx, cy - EY * (n_ramos + 1), 'V'))

    # Postes não alcançados pelo BFS
    max_x = max((n.x for n in postes_numerados if n.id in visitados), default=0)
    for no in postes_numerados:
        if no.id not in visitados:
            max_x += EX
            no.x = max_x
            no.y = 0.0

    # Equipamentos extras (transformadores sem poste, chaves extras)
    for no in nos.values():
        if not (no.id.startswith('P') and no.id[1:].isdigit()):
            # Busca poste associado
            vizinhos_eq = adj.get(no.id, [])
            if vizinhos_eq and vizinhos_eq[0] in nos:
                ref = nos[vizinhos_eq[0]]
                no.x = ref.x
                no.y = ref.y - EY
            else:
                # Coloca ao centro-baixo
                cx = sum(n.x for n in postes_numerados) / max(len(postes_numerados), 1)
                no.x = cx
                no.y = -EY * 2

    _normalizar_posicoes(nos)


def _normalizar_posicoes(nos: Dict[str, NoRede]):
    """Normaliza posições para caber na área de desenho."""
    if not nos:
        return

    xs = [n.x for n in nos.values()]
    ys = [n.y for n in nos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    largura = max_x - min_x or 1
    altura = max_y - min_y or 1

    # Escala para caber em 20x12 unidades
    escala_x = 20.0 / largura
    escala_y = 12.0 / altura
    escala = min(escala_x, escala_y, 1.5)  # não aumenta demais

    for no in nos.values():
        no.x = (no.x - min_x) * escala
        no.y = (no.y - min_y) * escala
