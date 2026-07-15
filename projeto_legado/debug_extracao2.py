"""
Testa diferentes métodos de extração para achar os IDs corretos.
"""
import re
import pdfplumber

PROJETOS = [
    {
        'nome': 'Projeto 1',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\300001108116PROJETOA3_20260224172732.202_X.pdf',
        'ids_croqui_real': ['689692', '689726', '689749', '745255', '761619', '1212634', '1212618', '772134', '689648'],
    },
    {
        'nome': 'Projeto 2',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\300001056564 PROJETO A1.pdf',
        'ids_croqui_real': ['626460', '690199', '690376', '1100897'],
    },
    {
        'nome': 'Projeto 3',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\7069897PROJETOA2_2FL_20260302161723.810_X.pdf',
        'ids_croqui_real': ['691102', '690815', '626614', '764405', '116079', '1155006', '1232519', '1281226'],
    },
]

def metodo1_extract_text(caminho):
    """extract_text() padrão + regex."""
    ids = set()
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            texto = page.extract_text(x_tolerance=3, y_tolerance=3) or ''
            for m in re.findall(r'\b\d{6,7}\b', texto):
                if int(m) >= 100000 and not m.startswith('300001'):
                    ids.add(m)
    return ids

def metodo2_chars_direto(caminho):
    """Chars direto: collapse todos os dígitos próximos em qualquer direção."""
    ids = set()
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            chars = [c for c in (page.chars or [])
                     if c['text'].isdigit()
                     and 0 <= c['x0'] <= page.width
                     and 0 <= c['top'] <= page.height]

            if not chars:
                continue

            # Clusteriza por proximidade 2D (vizinhos a 20pt)
            usado = [False] * len(chars)
            for i, c in enumerate(chars):
                if usado[i]:
                    continue
                cluster = [c]
                usado[i] = True
                for j, c2 in enumerate(chars):
                    if usado[j]:
                        continue
                    if (abs(c2['x0'] - c['x0']) < 20 and
                        abs(c2['top'] - c['top']) < 20):
                        cluster.append(c2)
                        usado[j] = True

                cluster.sort(key=lambda x: (round(x['top']/6)*6, x['x0']))
                num = ''.join(d['text'] for d in cluster)
                if len(num) in (6, 7) and int(num) >= 100000:
                    ids.add(num)
    return ids

def metodo3_words_largas(caminho):
    """extract_words com tolerâncias maiores."""
    ids = set()
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            # Tenta várias tolerâncias
            for xt, yt in [(10, 10), (20, 10), (30, 15)]:
                words = page.extract_words(x_tolerance=xt, y_tolerance=yt)
                for w in words:
                    for m in re.findall(r'\d{6,7}', w['text']):
                        if int(m) >= 100000 and not m.startswith('300001'):
                            ids.add(m)
    return ids

def metodo4_text_layout(caminho):
    """extract_text com layout=True preserva mais posições."""
    ids = set()
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            try:
                texto = page.extract_text(layout=True) or ''
            except Exception:
                texto = page.extract_text() or ''
            for m in re.findall(r'\d{6,7}', texto):
                if int(m) >= 100000 and not m.startswith('300001'):
                    ids.add(m)
    return ids

for par in PROJETOS:
    print(f"\n{'='*60}")
    print(f"{par['nome']}")
    real = set(par['ids_croqui_real'])
    print(f"IDs reais: {sorted(real)}")

    for nome, fn in [
        ('metodo1_extract_text', metodo1_extract_text),
        ('metodo2_chars_2D',     metodo2_chars_direto),
        ('metodo3_words_largas', metodo3_words_largas),
        ('metodo4_text_layout',  metodo4_text_layout),
    ]:
        try:
            encontrados = fn(par['projeto'])
            acertos = encontrados & real
            print(f"  {nome}: encontrou {len(encontrados)} IDs, acertou {len(acertos)}/{len(real)}: {sorted(acertos)}")
        except Exception as e:
            print(f"  {nome}: ERRO {e}")
