"""
Testa OCR: renderiza o PDF como imagem e usa pytesseract para extrair IDs.
Usa lang='eng' e modo digits para extrair apenas números.
"""
import re
import fitz
import pytesseract
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

PROJETOS = [
    {
        'nome': 'Projeto 1',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\300001108116PROJETOA3_20260224172732.202_X.pdf',
        'ids_reais': ['689692', '689726', '689749', '745255', '761619', '1212634', '1212618', '772134', '689648'],
    },
    {
        'nome': 'Projeto 2',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\300001056564 PROJETO A1.pdf',
        'ids_reais': ['626460', '690199', '690376', '1100897'],
    },
    {
        'nome': 'Projeto 3',
        'projeto': r'E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\7069897PROJETOA2_2FL_20260302161723.810_X.pdf',
        'ids_reais': ['691102', '690815', '626614', '764405', '116079', '1155006', '1232519', '1281226'],
    },
]


def extrair_com_ocr(caminho, dpi=200):
    """Renderiza PDF como imagem e aplica OCR."""
    ids_com_pos = {}
    doc = fitz.open(caminho)

    for page_num, page in enumerate(doc):
        # Renderiza a página como imagem em escala de cinza
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        escala = 72 / dpi  # converte pixels → pts PDF

        # OCR completo em inglês
        try:
            dados = pytesseract.image_to_data(
                img,
                lang='eng',
                config='--psm 11 --oem 3',
                output_type=pytesseract.Output.DICT
            )

            for i, texto in enumerate(dados['text']):
                if not texto or dados['conf'][i] < 30:
                    continue
                for m in re.findall(r'\d{6,7}', texto):
                    if int(m) >= 100000 and not m.startswith('300001'):
                        x = dados['left'][i] * escala
                        y = dados['top'][i] * escala
                        ids_com_pos[m] = (x, y)
        except Exception as e:
            print(f"  OCR erro pagina {page_num}: {e}")

    doc.close()
    return ids_com_pos


for par in PROJETOS:
    print(f"\n{'='*60}")
    print(f"{par['nome']}")
    real = set(par['ids_reais'])
    print(f"IDs reais: {sorted(real)}")

    try:
        encontrados = extrair_com_ocr(par['projeto'], dpi=200)
        acertos = set(encontrados.keys()) & real
        extras = set(encontrados.keys()) - real
        faltando = real - set(encontrados.keys())
        print(f"OCR acertou {len(acertos)}/{len(real)}: {sorted(acertos)}")
        print(f"Faltando ainda: {sorted(faltando)}")
        print(f"Extras (total {len(extras)}): {sorted(list(extras))[:15]}")
    except Exception as e:
        import traceback
        print(f"ERRO: {e}")
        traceback.print_exc()
