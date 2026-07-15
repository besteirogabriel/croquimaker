"""
Debug: compara IDs no projeto PDF com IDs no croqui real.
"""
import re
import pdfplumber

PROJETOS = [
    {
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\300001108116PROJETOA3_20260224172732.202_X.pdf',
        'croqui':  r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\croqui TR 689692 tes.pdf',
    },
    {
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\300001056564 PROJETO A1.pdf',
        'croqui':  r'E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\croqui fu 626460.pdf',
    },
    {
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\7069897PROJETOA2_2FL_20260302161723.810_X.pdf',
        'croqui':  r'E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\croqui rl 116079 TES 01.pdf',
    },
    {
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 4 + Croqui\7083647 PROJETO A3.pdf',
        'croqui':  r'E:\Projetos\CLAUDE IA\Croqui\Projeto 4 + Croqui\croqui TR 691446.pdf',
    },
    {
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 5 + Croqui\300001068717ProjetoA1_3FL_20260402121011.829_X.pdf',
        'croqui':  r'E:\Projetos\CLAUDE IA\Croqui\Projeto 5 + Croqui\croqui FU 626634.pdf',
    },
]

def extrair_ids_texto(caminho):
    """Extrai IDs de 6-7 dígitos do texto do PDF via palavras."""
    ids = {}
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=5, y_tolerance=5)
            for w in words:
                # Encontra 6-7 dígitos no texto da palavra
                matches = re.findall(r'\d{6,7}', w['text'])
                for m in matches:
                    if int(m) >= 100000:
                        cx = (w['x0'] + w['x1']) / 2
                        cy = (w['top'] + w['bottom']) / 2
                        ids[m] = (cx, cy)
    return ids

def extrair_ids_croqui(caminho):
    """Extrai IDs do croqui REAL - somente da área de desenho (acima da tabela viabilidade)."""
    ids = {}
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            # Área de desenho: y < 60% da altura da página (acima da tabela)
            limite_y = page.height * 0.60
            words = page.extract_words(x_tolerance=5, y_tolerance=5)
            for w in words:
                if w['top'] > limite_y:
                    continue  # ignora tabela viabilidade
                if w['top'] < 80:
                    continue  # ignora cabeçalho
                matches = re.findall(r'\d{6,7}', w['text'])
                for m in matches:
                    if int(m) >= 100000:
                        cx = (w['x0'] + w['x1']) / 2
                        cy = (w['top'] + w['bottom']) / 2
                        ids[m] = (cx, cy)
    return ids

print("="*70)
for i, par in enumerate(PROJETOS, 1):
    print(f"\nPROJETO {i}:")

    ids_proj = extrair_ids_texto(par['projeto'])
    ids_croqui = extrair_ids_croqui(par['croqui'])

    print(f"  IDs no projeto: {sorted(ids_proj.keys())}")
    print(f"  IDs no croqui:  {sorted(ids_croqui.keys())}")

    comuns = set(ids_proj.keys()) & set(ids_croqui.keys())
    so_croqui = set(ids_croqui.keys()) - set(ids_proj.keys())
    so_projeto = set(ids_proj.keys()) - set(ids_croqui.keys())

    print(f"  COMUNS ({len(comuns)}): {sorted(comuns)}")
    print(f"  No croqui mas NAO no projeto: {sorted(so_croqui)}")
    print(f"  No projeto mas NAO no croqui: {sorted(so_projeto)}")
