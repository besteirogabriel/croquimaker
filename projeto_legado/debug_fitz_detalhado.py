"""
Testa extração fitz com dict mode e span-level para achar todos os IDs.
"""
import re
import fitz

caminho = r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\300001108116PROJETOA3_20260224172732.202_X.pdf'
ids_reais = ['689692', '689726', '689749', '745255', '761619', '1212634', '1212618', '772134', '689648']

doc = fitz.open(caminho)
page = doc[0]

print(f"Pagina: {page.rect}")
print()

# Tenta get_text('dict') - nível de span
dict_data = page.get_text('dict')
print(f"Blocos no dict: {len(dict_data['blocks'])}")

todos_textos = []
for block in dict_data['blocks']:
    if block.get('type') != 0:
        continue
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            t = span.get('text', '').strip()
            if t:
                bbox = span.get('bbox', (0,0,0,0))
                todos_textos.append({
                    'text': t,
                    'x': (bbox[0]+bbox[2])/2,
                    'y': (bbox[1]+bbox[3])/2,
                    'bbox': bbox,
                })

print(f"Total spans com texto: {len(todos_textos)}")
print()

# Procura IDs reais
print("=== Buscando IDs reais nos spans ===")
for id_real in ids_reais:
    encontrado = False
    for t in todos_textos:
        if id_real in t['text']:
            print(f"  ENCONTRADO '{id_real}' em '{t['text']}' @ ({t['x']:.0f}, {t['y']:.0f})")
            encontrado = True
    if not encontrado:
        print(f"  NAO encontrado: '{id_real}'")

print()
print("=== Todos os spans com 6+ dígitos ===")
for t in todos_textos:
    nums = re.findall(r'\d{5,7}', t['text'])
    for n in nums:
        if int(n) >= 100000:
            print(f"  '{n}' em '{t['text'][:40]}' @ ({t['x']:.0f}, {t['y']:.0f})")

doc.close()
