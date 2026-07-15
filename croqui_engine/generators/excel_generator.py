from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.output.contract import main_equipment_label_from_payload, output_header_values
from croqui_engine.rendering.final_croqui_renderer import generate_final_croqui_pdf
from croqui_engine.storage.file_store import sanitize_name

CROQUI_COL_WIDTHS = [
    402,
    11190,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    4278,
    1353,
    1353,
    1353,
    1353,
    1353,
    1353,
    2486,
    1353,
    5558,
    3949,
    694,
    6070,
    694,
    694,
    694,
    694,
    694,
    694,
    694,
    694,
    694,
    694,
    694,
    1426,
    694,
    1097,
    694,
    841,
    694,
    694,
    1865,
    3840,
    21284,
    2377,
]
CROQUI_ROW_HEIGHTS = [
    300,
    300,
    240,
    225,
    360,
    360,
    1249,
    300,
    300,
    1005,
    300,
    818,
    300,
    1080,
    255,
    225,
    255,
    255,
    255,
    255,
    255,
    765,
    300,
    300,
    300,
    300,
    300,
    1020,
    945,
    289,
    1530,
    360,
    345,
    345,
    345,
    345,
    345,
    345,
    345,
    345,
    345,
    345,
    360,
    315,
    315,
]

VIABILITY_ROWS = [
    ("Foi realizada a avaliação do TIPO DE SOLO para permitir executar este Obra ?", "Sim"),
    (
        "Foi realizada uma AVALIAÇÃO EM CAMPO do Poste ou dos Equipamentos, se estes apresentam as "
        "condições de operação para realizar as Manobras?",
        "Sim",
    ),
    (
        "Foi realizada uma AVALIAÇÃO EM CAMPO para verificar a compatibilidade do condutor nos casos "
        "de trabalhos de equipes de Linha Viva (Solicitação /DIRA) ?",
        "Sim",
    ),
    ("Caso seja necessário uma PREPARAÇÃO para execução da Obra, ela já foi realizada?", "Sim"),
    ("Existe VEÍCULO RESERVA no dia do desligamento, caso necessite?", "Sim"),
    ("Se a execução afetar o CLIENTE, ele concorda com a intervenção?", "Sim"),
    ("O MATERIAL para esta obra está disponível?", "Sim"),
    (
        "O Tempo para execução está adequado e evita possibilidades de ATRASOS na execução ou no "
        "deslocamento para a obra?",
        "Sim",
    ),
    ("Está previsto outro DOCUMENTO RESERVA para esta obra, que será cancelado posteriormente?", "Sim"),
    ("Este documento já foi CANCELADO ou é uma Reprogramação?", "Não"),
]


def generate_excel(
    payload: TechnicalPayload,
    output_path: Path,
    template_path: Path | None = None,
    source_pdf_path: Path | None = None,
) -> Path:
    return _generate_structured_xls(payload, output_path, template_path)


def default_excel_name(payload: TechnicalPayload) -> str:
    tes = sanitize_name(str(payload.meta.get("tes_number", "sem_tes")))
    municipio = sanitize_name(str(payload.meta.get("municipality", "municipio")))
    return f"croqui_TES_{tes}_{municipio}.xls"


def _generate_from_template(
    payload: TechnicalPayload,
    output_path: Path,
    template_path: Path,
    source_pdf_path: Path | None = None,
) -> Path:
    import xlrd
    import xlwt
    from xlutils.copy import copy as xl_copy

    output_path.parent.mkdir(parents=True, exist_ok=True)
    book = xlrd.open_workbook(str(template_path), formatting_info=True)
    writable = xl_copy(book)
    sheet = writable.get_sheet(0)
    _configure_croqui_page(sheet)
    style = xlwt.XFStyle()
    font = xlwt.Font()
    font.name = "Arial"
    font.height = 200
    style.font = font
    sheet.write(4, 8, payload.meta.get("department", ""), style)
    sheet.write(4, 26, str(payload.meta.get("municipality", "")).upper(), style)
    equipment_label = _main_equipment_label(payload)
    sheet.write(4, 41, equipment_label, style)
    sheet.write(5, 8, payload.meta.get("survey_date", ""), style)
    sheet.write(5, 33, payload.meta.get("surveyor", payload.meta.get("levantador", "")), style)
    _write_viability_defaults(sheet, style, template_path)
    _insert_final_croqui_drawing(sheet, payload, output_path)
    writable.save(str(output_path))
    return output_path


def _generate_structured_xls(
    payload: TechnicalPayload,
    output_path: Path,
    template_path: Path | None = None,
) -> Path:
    import xlwt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlwt.Workbook()
    sheet = wb.add_sheet("Croqui v1")
    _configure_croqui_page(sheet)
    _setup_croqui_grid(sheet)
    styles = _croqui_styles()
    try:
        sheet.set_header_str(b"")
        sheet.set_footer_str(b"")
    except Exception:
        pass
    _write_rge_logo(sheet, output_path.parent)
    _write_xls_header(sheet, payload, styles)
    _write_xls_drawing_area(sheet, payload, output_path, styles)
    _write_xls_viability(sheet, styles)
    _write_xls_legends(sheet, styles)

    _sheet_rows(
        wb,
        "Dados",
        [
            ("Campo", "Valor"),
            ("Departamento", payload.meta.get("department", "")),
            ("Municipio", str(payload.meta.get("municipality", "")).upper()),
            ("Equipamento", _main_equipment_label(payload)),
            ("Data do levantamento", payload.meta.get("survey_date", "")),
            ("Levantamento de campo realizado por", payload.meta.get("surveyor", "")),
            ("Confianca", payload.confidence_global),
            ("Modo", "Gerado ao vivo a partir do PDF enviado"),
        ],
    )
    _write_symbol_sheet(wb)
    wb.save(str(output_path))
    return output_path


def _setup_croqui_grid(sheet) -> None:
    try:
        sheet.show_grid = False
    except Exception:
        pass
    for col in range(49):
        if col == 0:
            width = 300
        elif col >= 42:
            width = 900
        else:
            width = 720
        sheet.col(col).width = width
    for row, height in enumerate(CROQUI_ROW_HEIGHTS):
        sheet.row(row).height = height


def _croqui_styles() -> dict[str, object]:
    import xlwt

    return {
        "label": _xls_style(xlwt, height=100, bold=True, border=True),
        "value": _xls_style(xlwt, height=100, border=True, align="center"),
        "drawing": _xls_style(xlwt, border=True),
        "yellow": _xls_style(xlwt, height=90, bold=True, border=True, fill=5, font_color=2, align="center"),
        "question": _xls_style(xlwt, height=85, border=True, wrap=True),
        "question_gray": _xls_style(xlwt, height=85, border=True, fill=22, wrap=True),
        "answer": _xls_style(xlwt, height=85, bold=True, border=True, align="center"),
        "answer_gray": _xls_style(xlwt, height=85, bold=True, border=True, fill=22, align="center"),
        "legend": _xls_style(xlwt, height=90, border=False, wrap=True),
        "blank": _xls_style(xlwt, border=False),
    }


def _xls_style(
    xlwt,
    *,
    height: int = 90,
    bold: bool = False,
    border: bool = False,
    fill: int | None = None,
    font_color: int | None = None,
    align: str = "left",
    wrap: bool = False,
):
    style = xlwt.XFStyle()
    font = xlwt.Font()
    font.name = "Arial"
    font.height = height
    font.bold = bold
    if font_color is not None:
        font.colour_index = font_color
    style.font = font

    alignment = xlwt.Alignment()
    alignment.horz = {
        "left": xlwt.Alignment.HORZ_LEFT,
        "center": xlwt.Alignment.HORZ_CENTER,
        "right": xlwt.Alignment.HORZ_RIGHT,
    }.get(align, xlwt.Alignment.HORZ_LEFT)
    alignment.vert = xlwt.Alignment.VERT_CENTER
    alignment.wrap = int(wrap)
    style.alignment = alignment

    if border:
        borders = xlwt.Borders()
        borders.left = xlwt.Borders.THIN
        borders.right = xlwt.Borders.THIN
        borders.top = xlwt.Borders.THIN
        borders.bottom = xlwt.Borders.THIN
        style.borders = borders

    if fill is not None:
        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = fill
        style.pattern = pattern
    return style


def _write_rge_logo(sheet, output_dir: Path) -> None:
    bmp = _make_rge_logo_bmp(output_dir / "rge_logo_xls.bmp")
    try:
        sheet.insert_bitmap(str(bmp), 1, 1, x=2, y=2, scale_x=0.78, scale_y=0.78)
    except Exception:
        import xlwt

        style = _xls_style(xlwt, height=420, bold=True)
        sheet.write_merge(1, 3, 1, 7, "RGE", style)


def _make_rge_logo_bmp(path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (360, 86), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial Bold Italic.ttf", 48)
        small = ImageFont.truetype("Arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    draw.text((2, 10), "RGE", fill=(0, 0, 0), font=font)
    draw.text((84, 34), "Rio GrandeEnergia", fill=(0, 0, 0), font=small)
    draw.line((166, 42, 346, 42), fill=(0, 0, 0), width=2)
    draw.ellipse((344, 40, 348, 44), fill=(0, 0, 0), outline=(0, 0, 0))
    img.save(path, format="BMP")
    return path


def _write_xls_header(sheet, payload: TechnicalPayload, styles: dict[str, object]) -> None:
    values = output_header_values(payload)
    sheet.write_merge(4, 4, 1, 6, "Departamento:", styles["label"])
    sheet.write_merge(4, 4, 8, 14, values["department"], styles["value"])
    sheet.write_merge(4, 4, 15, 21, "Município:", styles["label"])
    sheet.write_merge(4, 4, 23, 32, values["municipality"], styles["value"])
    sheet.write_merge(4, 4, 33, 40, "Equipamento :", styles["label"])
    sheet.write_merge(4, 4, 41, 48, values["equipment"], styles["value"])

    sheet.write_merge(5, 5, 1, 6, "Data do Levantamento:", styles["label"])
    sheet.write_merge(5, 5, 8, 14, values["survey_date"], styles["value"])
    sheet.write_merge(5, 5, 15, 31, "Levantamento de campo realizado por:", styles["label"])
    sheet.write_merge(5, 5, 33, 48, values["surveyor"], styles["value"])


def _write_xls_drawing_area(
    sheet,
    payload: TechnicalPayload,
    output_path: Path,
    styles: dict[str, object],
) -> None:
    sheet.write_merge(6, 30, 1, 47, "", styles["drawing"])
    _insert_final_croqui_drawing(sheet, payload, output_path)


def _write_xls_viability(sheet, styles: dict[str, object]) -> None:
    sheet.write(28, 48, "Sim", styles["answer"])
    sheet.write(29, 48, "Não", styles["answer"])
    sheet.write(30, 48, "Não Avaliado", styles["answer"])
    sheet.write_merge(
        31,
        31,
        1,
        41,
        "                      Avaliação de Viabilidade                     * Preenchimento obrigatório com Sim, Não ou Não Avaliado",
        styles["yellow"],
    )
    sheet.write_merge(31, 31, 42, 45, "Viabilidade:", styles["yellow"])
    sheet.write_merge(31, 31, 46, 48, "100,0%", styles["yellow"])
    for index, (question, answer) in enumerate(VIABILITY_ROWS, start=32):
        gray = (index - 32) % 2 == 1
        question_style = styles["question_gray"] if gray else styles["question"]
        answer_style = styles["answer_gray"] if gray else styles["answer"]
        sheet.write_merge(index, index, 1, 41, question, question_style)
        sheet.write_merge(index, index, 42, 47, answer, answer_style)
        sheet.write(index, 48, 0 if answer == "Não" else 1, answer_style)


def _write_xls_legends(sheet, styles: dict[str, object]) -> None:
    sheet.write_merge(
        42,
        42,
        1,
        48,
        "Legenda ação:    D - Desligar   L - Ligar   A - Abrir   F - Fechar   I - Incluir  E - Excluir",
        styles["legend"],
    )
    sheet.write_merge(
        43,
        44,
        1,
        48,
        "Legenda Tipo Equipamento:   FC - Chave faca    FU - Chave fusível    RL - Religador    RG - Regulador    OL - Chave óleo\n"
        "   SC - Seccionalizadora  TR - Transformador   TOM - Tomada particular de AT   OMR - Chave de operação sob carga",
        styles["legend"],
    )


def _main_equipment_label(payload: TechnicalPayload) -> str:
    return main_equipment_label_from_payload(payload)


def _write_viability_defaults(sheet, style, template_path: Path) -> None:
    rows = []
    if not rows:
        rows = [
            {"row": row, "answer": "Sim" if row < 41 else "Não"}
            for row in range(32, 42)
        ]
    try:
        sheet.write(31, 46, "100,0%", style)
    except Exception:
        pass
    for item in rows:
        row = int(item.get("row", 0))
        if not row:
            continue
        try:
            sheet.write(row, 42, item.get("answer") or ("Não" if row == 41 else "Sim"), style)
        except Exception:
            continue


def _configure_croqui_page(sheet) -> None:
    try:
        sheet.set_portrait(False)
        sheet.paper_size_code = 9
        sheet.set_fit_width_to_pages(1)
        sheet.set_fit_height_to_pages(1)
        sheet.set_fit_num_pages(1)
        sheet.set_print_scaling(100)
        sheet.set_print_centered_horz(True)
        sheet.set_print_centered_vert(False)
        sheet.set_header_str(b"&CCroqui")
        sheet.set_footer_str(b"")
        sheet.set_left_margin(0.15)
        sheet.set_right_margin(0.15)
        sheet.set_top_margin(0.20)
        sheet.set_bottom_margin(0.20)
        sheet.set_horz_page_breaks([])
        sheet.set_vert_page_breaks([])
    except Exception:
        return


def _insert_final_croqui_drawing(sheet, payload: TechnicalPayload, output_path: Path) -> None:
    try:
        from croqui_engine.rendering.final_croqui_renderer import generate_croqui_drawing_bmp

        bmp = generate_croqui_drawing_bmp(payload, output_path.parent / "croqui_desenho_final.bmp")
        # Area aproximada do desenho oficial: cabecalho acima, viabilidade abaixo.
        sheet.insert_bitmap(str(bmp), 7, 1, x=8, y=4, scale_x=0.92, scale_y=0.92)
    except Exception:
        return


def _final_pdf_page_to_bmp(payload: TechnicalPayload, bmp_path: Path) -> Path:
    import fitz
    from PIL import Image

    pdf_path = bmp_path.with_suffix(".pdf")
    generate_final_croqui_pdf(payload, pdf_path)
    with fitz.open(pdf_path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        png_bytes = pix.tobytes("png")
    import io

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    image.save(bmp_path, format="BMP")
    return bmp_path


def _write_symbol_sheet(wb) -> None:
    import xlwt

    sheet = wb.add_sheet("Simbologia")
    _configure_croqui_page(sheet)
    try:
        sheet.set_header_str(b"")
        sheet.set_footer_str(b"")
    except Exception:
        pass
    try:
        sheet.show_grid = False
    except Exception:
        pass
    for col in range(51):
        sheet.col(col).width = 520
    for col in (8, 25, 42):
        for extra in range(9):
            sheet.col(col + extra).width = 780
    for row in range(82):
        sheet.row(row).height = 300

    title = _xls_style(xlwt, height=180, bold=True, border=False, align="center")
    header = _xls_style(xlwt, height=110, bold=True, border=True, fill=22, align="center")
    symbol_style = _xls_style(xlwt, height=220, bold=True, border=True, align="center", wrap=True)
    desc_style = _xls_style(xlwt, height=105, border=True, wrap=True)

    sheet.write_merge(4, 4, 1, 48, "Simbologia básica para identificação nos croquis", title)
    groups = [(1, 8), (18, 25), (35, 42)]
    for symbol_col, desc_col in groups:
        sheet.write_merge(6, 6, symbol_col, symbol_col + 6, "Símbolo", header)
        sheet.write_merge(6, 6, desc_col, desc_col + 8, "Descrição", header)

    symbols = _official_symbol_rows()
    grouped = [symbols[0:12], symbols[12:24], symbols[24:36]]
    for group, (symbol_col, desc_col) in zip(grouped, groups, strict=False):
        for index, (marker, description) in enumerate(group):
            row = 7 + index * 3
            sheet.row(row).height = 430
            sheet.row(row + 1).height = 430
            sheet.write_merge(row, row + 1, symbol_col, symbol_col + 6, marker, symbol_style)
            sheet.write_merge(row, row + 1, desc_col, desc_col + 8, description, desc_style)

    sheet.write_merge(46, 46, 1, 48, "Simbologia básica para identificação nos croquis", title)


def _official_symbol_rows() -> list[tuple[str, str]]:
    return [
        ("○", "Poste existente"),
        ("◉", "Poste a ser instalado novo ou a ser substituído"),
        ("--●--", "Cruzamento de condutores com conexão"),
        ("-- --", "Cruzamento de condutores sem conexão"),
        ("──", "Passagem de condutor Primário"),
        ("- - -", "Passagem de condutor Secundário"),
        ("═", "Passagem de condutor Primário e Secundário"),
        ("⊣", "Encabeçamento ou mudança de bitola de condutor Primário"),
        ("⊢", "Encabeçamento ou mudança de bitola de condutor Secundário"),
        ("FU-R", "Chave fusível Religadora"),
        ("FU", "Chave fusível sem abertura em carga"),
        ("FU-C", "Chave fusível com abertura em carga"),
        ("P", "Seccionamento do Primário"),
        ("S", "Seccionamento do Secundário"),
        ("TR", "Transformador da concessionária"),
        ("TOM", "Medidor primário / Transformador particular"),
        ("RL", "Religador"),
        ("SC", "Seccionalizadora"),
        ("BC", "Banco de Capacitor"),
        ("RG", "Regulador de tensão"),
        ("OL-1", "Chave a óleo Unipolar"),
        ("OL-3", "Chave a óleo Tripolar"),
        ("FC", "Chave faca sem abertura em carga"),
        ("FC-C", "Chave faca com abertura em carga"),
        ("3FC", "Chave faca tripolar sem abertura em carga"),
        ("3FC-C", "Chave faca tripolar com abertura em carga"),
        ("OMR", "Chave Omni-rupter / operação sob carga"),
        ("AT-BT", "Aterramento temporário de Baixa Tensão"),
        ("AT-MT", "Aterramento temporário de Alta Tensão"),
        ("□", "A área de trabalho deve ser delimitada por linha tracejada vermelha"),
        ("Área 1", "Área de trabalho 1"),
        ("Área 2", "Área de trabalho 2"),
        ("08-10", "Identificação de horário da área de trabalho"),
        ("MEP", "Isolação conforme MEP quando aplicável"),
        ("D/L", "Desligar ou ligar equipamento"),
        ("A/F", "Abrir ou fechar equipamento"),
    ]


def _generate_simple_xls(payload: TechnicalPayload, output_path: Path) -> Path:
    import xlwt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlwt.Workbook()

    _sheet_rows(
        wb,
        "Resumo",
        [
            ("Campo", "Valor"),
            ("Job", payload.job_id or ""),
            ("TES", payload.meta.get("tes_number", "")),
            ("Municipio", payload.meta.get("municipality", "")),
            ("Equipamento principal", payload.meta.get("main_switching_equipment", "")),
            ("Confianca", payload.confidence_global),
            ("Engine", payload.engine_version),
        ],
    )
    _sheet_rows(
        wb,
        "Equipamentos",
        [("Codigo", "Tipo", "Poste", "Status", "Confianca", "Texto")]
        + [
            (e.code, e.type, e.node_id or "", e.status or "", e.confidence, e.raw_text or "")
            for e in payload.active_equipment()
        ],
    )
    _sheet_rows(
        wb,
        "Postes",
        [("ID", "Tipo", "X", "Y", "Pagina", "Confianca")]
        + [(n.id, n.type, n.x or "", n.y or "", n.page_index or "", n.confidence) for n in payload.active_nodes()],
    )
    _sheet_rows(
        wb,
        "Vaos",
        [("ID", "De", "Para", "Comprimento", "Cabo", "Tipo", "Confianca", "Texto")]
        + [
            (
                s.id,
                s.from_node,
                s.to_node,
                s.length_m or "",
                s.cable or "",
                s.network_type or "",
                s.confidence,
                s.raw_text or "",
            )
            for s in payload.active_spans()
        ],
    )
    _sheet_rows(
        wb,
        "Validacoes",
        [("Severidade", "Codigo", "Mensagem", "Objeto", "Acao sugerida")]
        + [
            (
                v.severity,
                v.code,
                v.message,
                f"{v.object_type or ''}:{v.object_id or ''}",
                v.suggested_action or "",
            )
            for v in payload.validations
        ],
    )

    wb.save(str(output_path))
    return output_path


def _sheet_rows(wb, name: str, rows: list[tuple]) -> None:
    sheet = wb.add_sheet(name[:31])
    header_style = _header_style()
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            sheet.write(r, c, value, header_style if r == 0 else _normal_style())
        if r == 0:
            for c in range(len(row)):
                sheet.col(c).width = 5000


def _header_style():
    import xlwt

    style = xlwt.XFStyle()
    font = xlwt.Font()
    font.bold = True
    style.font = font
    return style


def _normal_style():
    import xlwt

    style = xlwt.XFStyle()
    font = xlwt.Font()
    font.name = "Arial"
    font.height = 180
    style.font = font
    return style
