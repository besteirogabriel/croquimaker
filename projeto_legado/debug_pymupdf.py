"""
Testa extração com PyMuPDF para os IDs corretos.
"""
import re
import fitz  # PyMuPDF

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
    {
        'nome': 'Projeto 4',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 4 + Croqui\7083647 PROJETO A3.pdf',
        'ids_croqui_real': ['691446', '690866', '626636', '1110594', '1071291'],
    },
    {
        'nome': 'Projeto 5',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 5 + Croqui\300001068717ProjetoA1_3FL_20260402121011.829_X.pdf',
        'ids_croqui_real': ['626634', '690884', '757782', '757783', '757784', '626776', '936355'],
    },
]

def extrair_com_fitz(caminho):
    """Extrai IDs com PyMuPDF (fitz), inclui posição X,Y."""
    ids = {}
    doc = fitz.open(caminho)
    for page in doc:
        # Extrai blocos de texto com posição
        blocks = page.get_text('blocks')
        for b in blocks:
            x0, y0, x1, y1, texto, _, _ = b
            for m in re.findall(r'\d{5,7}', texto):
                v = int(m)
                if v >= 100000 and not m.startswith('300001') and not m.startswith('30000'):
                    cx = (x0 + x1) / 2
                    cy = (y0 + y1) / 2
                    ids[m] = (cx, cy)

        # Extrai palavras individuais com posição
        words = page.get_text('words')
        for w in words:
            x0, y0, x1, y1, texto = w[:5]
            for m in re.findall(r'\d{5,7}', texto):
                v = int(m)
                if v >= 100000 and not m.startswith('300001') and not m.startswith('30000'):
                    cx = (x0 + x1) / 2
                    cy = (y0 + y1) / 2
                    ids[m] = (cx, cy)

    doc.close()
    return ids

def extrair_chars_fitz(caminho):
    """Extrai caracteres individuais com posição e reconstrói IDs."""
    ids = {}
    doc = fitz.open(caminho)
    for page in doc:
        # Extrai dicionário de texto (mais detalhado)
        dict_text = page.get_text('rawdict')
        for block in dict_text.get('blocks', []):
            if block.get('type') != 0:
                continue
            for line in block.get('lines', []):
                # Coleta todos os spans da linha
                texto_linha = ''
                for span in line.get('spans', []):
                    texto_linha += span.get('text', '')
                # Busca IDs no texto da linha
                for m in re.findall(r'\d{6,7}', texto_linha):
                    v = int(m)
                    if v >= 100000 and not m.startswith('300001') and not m.startswith('30000'):
                        bbox = line.get('bbox', (0,0,0,0))
                        cx = (bbox[0] + bbox[2]) / 2
                        cy = (bbox[1] + bbox[3]) / 2
                        ids[m] = (cx, cy)
    doc.close()
    return ids

for par in PROJETOS:
    print(f"\n{'='*60}")
    print(f"{par['nome']}")
    real = set(par['ids_croqui_real'])
    print(f"IDs reais: {sorted(real)}")

    for nome, fn in [
        ('fitz_blocks_words', extrair_com_fitz),
        ('fitz_chars_rawdict', extrair_chars_fitz),
    ]:
        try:
            encontrados = fn(par['projeto'])
            acertos = set(encontrados.keys()) & real
            outros = set(encontrados.keys()) - real
            print(f"  {nome}: acertou {len(acertos)}/{len(real)}: {sorted(acertos)}")
            print(f"           extras: {sorted(outros)[:10]}")
        except Exception as e:
            import traceback
            print(f"  {nome}: ERRO {e}")
            traceback.print_exc()
