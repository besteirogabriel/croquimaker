"""
Tenta extrair a rede a partir de elementos gráficos (círculos/triângulos)
do PDF CAD, associando textos próximos.
"""
import re
import fitz
import math

caminho = r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\300001108116PROJETOA3_20260224172732.202_X.pdf'
ids_reais = ['689692', '689726', '689749', '745255', '761619', '1212634', '1212618', '772134', '689648']

doc = fitz.open(caminho)
page = doc[0]

# Extrai todos os desenhos gráficos
drawings = page.get_drawings()
print(f"Total de elementos gráficos: {len(drawings)}")

# Extrai todos os spans de texto com posição
spans_texto = []
dict_data = page.get_text('dict')
for block in dict_data['blocks']:
    if block.get('type') != 0:
        continue
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            t = span.get('text', '').strip()
            if t:
                bbox = span.get('bbox', (0,0,0,0))
                spans_texto.append({
                    'text': t,
                    'cx': (bbox[0]+bbox[2])/2,
                    'cy': (bbox[1]+bbox[3])/2,
                    'bbox': bbox,
                })

def texto_proximo(cx, cy, raio=60):
    """Retorna textos dentro do raio da posição."""
    resultado = []
    for s in spans_texto:
        dist = math.sqrt((s['cx']-cx)**2 + (s['cy']-cy)**2)
        if dist < raio:
            resultado.append((dist, s['text']))
    return sorted(resultado)

# Analisa os tipos de desenho
tipos = {}
for d in drawings:
    t = d.get('type', '?')
    tipos[t] = tipos.get(t, 0) + 1
print(f"Tipos de elementos: {tipos}")

# Procura por círculos/arcos (postes) e outras formas
print("\n=== Elementos com texto próximo que contém IDs ===")
for d in drawings:
    # Pega centro do elemento
    rect = d.get('rect', None)
    if rect is None:
        continue
    cx = (rect.x0 + rect.x1) / 2
    cy = (rect.y0 + rect.y1) / 2
    w = rect.x1 - rect.x0
    h = rect.y1 - rect.y0

    # Só elementos de tamanho razoável (símbolos de rede, não linhas)
    if max(w, h) < 5 or max(w, h) > 100:
        continue

    textos = texto_proximo(cx, cy, raio=80)
    ids_encontrados = []
    for dist, txt in textos:
        for m in re.findall(r'\d{6,7}', txt):
            if int(m) >= 100000:
                ids_encontrados.append((m, dist, txt))

    if ids_encontrados:
        tipo = d.get('type', '?')
        fill = d.get('fill', None)
        print(f"  Elemento {tipo} @ ({cx:.0f},{cy:.0f}) size=({w:.0f}x{h:.0f}) fill={fill}")
        for id_num, dist, txt in ids_encontrados:
            real = '*' if id_num in ids_reais else ' '
            print(f"    {real} ID={id_num} dist={dist:.0f} em '{txt}'")

# Procura por linhas que conectam símbolos
print("\n=== Tentando encontrar círculos específicos ===")
circulos = []
for d in drawings:
    if d.get('type') != 'f':  # 'f' = fill
        continue
    rect = d.get('rect', None)
    if rect is None:
        continue
    w = rect.x1 - rect.x0
    h = rect.y1 - rect.y0
    # Círculo: aspecto ratio próximo de 1
    if abs(w - h) < 3 and 8 < w < 40:
        cx = (rect.x0 + rect.x1) / 2
        cy = (rect.y0 + rect.y1) / 2
        circulos.append((cx, cy, w))

print(f"Círculos encontrados: {len(circulos)}")
for cx, cy, r in sorted(circulos, key=lambda x: x[1]):
    textos = texto_proximo(cx, cy, raio=100)
    nums = []
    for dist, txt in textos:
        for m in re.findall(r'\d{6,7}', txt):
            if int(m) >= 100000:
                nums.append(f"{m}(d={dist:.0f})")
    if nums:
        real_mark = any(n.split('(')[0] in ids_reais for n in nums)
        print(f"  {'*' if real_mark else ' '} cx={cx:.0f} cy={cy:.0f} r={r:.0f} nums={nums}")

doc.close()
