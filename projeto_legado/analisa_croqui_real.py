import pdfplumber
import os

arquivos = [
    r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\croqui TR 689692 tes.pdf',
    r'E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\croqui fu 626460.pdf',
    r'E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\croqui rl 116079 TES 01.pdf',
    r'E:\Projetos\CLAUDE IA\Croqui\Projeto 4 + Croqui\croqui TR 691446.pdf',
    r'E:\Projetos\CLAUDE IA\Croqui\Projeto 5 + Croqui\croqui FU 626634.pdf',
]

for caminho in arquivos:
    nome = caminho.split('\\')[-1]
    print(f"\n{'='*60}")
    print(f"ARQUIVO: {nome}")
    print('='*60)
    try:
        with pdfplumber.open(caminho) as pdf:
            print(f"Paginas: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages):
                print(f"\n--- Pag {i+1} ({page.width:.0f}x{page.height:.0f}) ---")
                # Extrai palavras com posição
                words = page.extract_words(x_tolerance=5, y_tolerance=5)
                print(f"Total palavras: {len(words)}")
                # Mostra todas as palavras com posição X,Y
                for w in words:
                    if len(w['text']) >= 3:  # só palavras com 3+ chars
                        print(f"  '{w['text']:25s}'  x={w['x0']:7.1f}  y={w['top']:7.1f}")
    except Exception as e:
        print(f"ERRO: {e}")
