from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.output.contract import output_header_values


def generate_croqui_pdf(
    payload: TechnicalPayload,
    output_path: Path,
    logo_path: Path | None = None,
    source_pdf_path: Path | None = None,
) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A3)
    c = canvas.Canvas(str(output_path), pagesize=(width, height))

    margin = 14 * mm
    header_h = 42 * mm
    footer_h = 16 * mm
    source_pdf = source_pdf_path if source_pdf_path and source_pdf_path.is_file() else None
    side_w = 0 if source_pdf else 92 * mm
    draw_x = margin
    draw_y = margin + footer_h
    draw_w = width - 2 * margin - side_w - 8 * mm
    draw_h = height - 2 * margin - header_h - footer_h
    side_x = draw_x + draw_w + 8 * mm

    _header(c, payload, logo_path, margin, height - margin - header_h, width - 2 * margin, header_h)
    if source_pdf:
        _draw_project_sheet(c, payload, source_pdf, draw_x, draw_y, width - 2 * margin, draw_h)
    else:
        _draw_graph(c, payload, draw_x, draw_y, draw_w, draw_h)
        _side_panel(c, payload, side_x, draw_y, side_w, draw_h)
    _footer(c, payload, margin, margin, width - 2 * margin, footer_h)

    c.setStrokeColor(colors.HexColor("#222222"))
    c.setLineWidth(0.8)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)
    _symbol_legend_page(c, width, height, margin, logo_path)
    c.save()
    return output_path


def generate_croqui_png(payload: TechnicalPayload, output_path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", 18)
        small = ImageFont.truetype("Arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.rectangle((20, 20, 1580, 980), outline=(30, 30, 30), width=2)
    draw.text((40, 36), "JOBEL Croqui Tecnico - Geracao Local", fill=(23, 32, 40), font=font)
    draw.text((40, 66), f"Confianca: {payload.confidence_global:.2f}", fill=(80, 80, 80), font=small)
    positions = _scaled_positions(payload, 80, 130, 1050, 760)
    for span in payload.active_spans():
        if span.from_node in positions and span.to_node in positions:
            draw.line([positions[span.from_node], positions[span.to_node]], fill=(12, 162, 248), width=3)
            mx = (positions[span.from_node][0] + positions[span.to_node][0]) / 2
            my = (positions[span.from_node][1] + positions[span.to_node][1]) / 2
            label = span.id
            if span.length_m:
                label += f" {span.length_m:.1f}m"
            draw.text((mx + 4, my - 16), label, fill=(50, 50, 50), font=small)
    for node in payload.active_nodes():
        if node.id not in positions:
            continue
        x, y = positions[node.id]
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), outline=(20, 20, 20), width=2, fill=(255, 255, 255))
        draw.text((x - 12, y + 13), node.id, fill=(20, 20, 20), font=small)
    for idx, eq in enumerate(payload.active_equipment()[:18]):
        y = 150 + idx * 34
        draw.text((1220, y), f"{eq.type} {eq.code} {eq.node_id or 'revisar'}", fill=(30, 30, 30), font=small)
    img.save(output_path)
    return output_path


def _header(c, payload, logo_path, x, y, w, h):
    from reportlab.lib import colors

    c.setFillColor(colors.HexColor("#F8FBFD"))
    c.rect(x, y + h * 0.45, w, h * 0.55, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0CA2F8"))
    c.rect(x, y + h * 0.45, w, h * 0.03, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.rect(x, y + h * 0.08, w, h * 0.37, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0CA2F8"))
    c.rect(x, y, w, h * 0.05, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#D5DDE3"))
    c.rect(x, y, w, h, fill=0, stroke=1)

    if logo_path and logo_path.exists() and logo_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        try:
            c.drawImage(str(logo_path), x + 8, y + h * 0.47, width=128, height=60, preserveAspectRatio=True)
        except Exception:
            _jobel_wordmark(c, x + 8, y + h * 0.65)
    else:
        _jobel_wordmark(c, x + 8, y + h * 0.65)

    c.setFillColor(colors.HexColor("#172028"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(x + 154, y + h * 0.69, "Croqui Tecnico - Geracao Local")
    c.setFont("Helvetica", 7)
    c.drawRightString(x + w - 8, y + h * 0.70, f"Engine {payload.engine_version}")

    header = output_header_values(payload)
    fields = [
        ("TES", payload.meta.get("tes_number", "")),
        ("Municipio", header.get("municipality", "")),
        ("Equipamento", header.get("equipment", "")),
        ("Processado", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Confianca", f"{payload.confidence_global:.2f}"),
    ]
    cw = w / len(fields)
    for i, (label, value) in enumerate(fields):
        cx = x + i * cw + 8
        c.setFillColor(colors.HexColor("#172028"))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(cx, y + h * 0.30, label)
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica", 8)
        c.drawString(cx, y + h * 0.16, str(value)[:38])


def _jobel_wordmark(c, x, y):
    from reportlab.lib import colors

    c.setFillColor(colors.HexColor("#0CA2F8"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x, y, "JOBEL")


def _draw_graph(c, payload: TechnicalPayload, x: float, y: float, w: float, h: float) -> None:
    from reportlab.lib import colors

    c.setFillColor(colors.HexColor("#FBFCFD"))
    c.setStrokeColor(colors.HexColor("#D5DDE3"))
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#282B2E"))
    c.drawString(x + 8, y + h - 14, "Grafo tecnico extraido")

    if not payload.active_nodes():
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawCentredString(x + w / 2, y + h / 2, "Nenhum poste identificado. Saida gerada para revisao.")
        return

    positions = _scaled_positions(payload, x + 32, y + 34, w - 64, h - 72, invert_y=True)
    for span in payload.active_spans():
        if span.from_node not in positions or span.to_node not in positions:
            continue
        x1, y1 = positions[span.from_node]
        x2, y2 = positions[span.to_node]
        c.setStrokeColor(colors.HexColor("#0CA2F8"))
        c.setLineWidth(1.4)
        if span.confidence < 0.7:
            c.setDash(5, 3)
            c.setStrokeColor(colors.HexColor("#7A8791"))
        else:
            c.setDash()
        c.line(x1, y1, x2, y2)
        c.setDash()
        label = span.id
        if span.length_m:
            label += f" {span.length_m:.2f}m"
        if span.cable:
            label += f" {span.cable}"
        c.setFillColor(colors.HexColor("#172028"))
        c.setFont("Helvetica", 6)
        c.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 4, label[:38])

    eq_by_node: dict[str, list] = {}
    for eq in payload.active_equipment():
        eq_by_node.setdefault(eq.node_id or "", []).append(eq)

    for node in payload.active_nodes():
        px, py = positions.get(node.id, (None, None))
        if px is None:
            continue
        c.setStrokeColor(colors.HexColor("#1B1B1B"))
        c.setFillColor(colors.white if node.confidence >= 0.7 else colors.HexColor("#EEEEEE"))
        c.circle(px, py, 4.2, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica", 6)
        c.drawCentredString(px, py - 12, node.id)
        ey = py + 9
        for eq in eq_by_node.get(node.id, [])[:3]:
            c.setFillColor(colors.HexColor("#531697") if eq.type == "TRANSFORMADOR" else colors.HexColor("#0A8BD6"))
            c.setFont("Helvetica-Bold", 6)
            c.drawCentredString(px, ey, f"{_eq_label(eq.type)} {eq.code}"[:18])
            ey += 8

    for area in payload.work_areas:
        if area.bbox:
            continue
        if payload.active_nodes():
            nodes = payload.active_nodes()[: min(4, len(payload.active_nodes()))]
            pts = [positions[n.id] for n in nodes if n.id in positions]
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                c.setStrokeColor(colors.HexColor("#D7332F"))
                c.setDash(6, 3)
                c.rect(min(xs) - 18, min(ys) - 18, max(xs) - min(xs) + 36, max(ys) - min(ys) + 36, fill=0, stroke=1)
                c.setDash()


def _draw_project_sheet(
    c,
    payload: TechnicalPayload,
    source_pdf_path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader

    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#D5DDE3"))
    c.rect(x, y, w, h, fill=1, stroke=1)
    try:
        import fitz

        page_index = _best_project_page_index(payload)
        with fitz.open(source_pdf_path) as doc:
            page_index = min(page_index, len(doc) - 1)
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            image = ImageReader(BytesIO(pix.tobytes("png")))
            scale = min(w / pix.width, h / pix.height)
            iw = pix.width * scale
            ih = pix.height * scale
            ix = x + (w - iw) / 2
            iy = y + (h - ih) / 2
            c.drawImage(image, ix, iy, width=iw, height=ih, mask="auto")
    except Exception:
        c.setFillColor(colors.HexColor("#666666"))
        c.setFont("Helvetica", 10)
        c.drawCentredString(x + w / 2, y + h / 2, "Nao foi possivel renderizar a folha de projeto.")
    _draw_extraction_summary_strip(c, payload, x, y, w)


def _draw_extraction_summary_strip(c, payload: TechnicalPayload, x: float, y: float, w: float) -> None:
    from reportlab.lib import colors

    strip_h = 22
    c.setFillColor(colors.HexColor("#FFF7C7"))
    c.setStrokeColor(colors.HexColor("#D5C562"))
    c.rect(x, y, w, strip_h, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#172028"))
    c.setFont("Helvetica-Bold", 7)
    equipment = payload.active_equipment()
    spans = payload.active_spans()
    corpus_case = payload.meta.get("corpus_case_id")
    text = (
        f"Gerado localmente a partir do projeto bruto | Equipamentos: {len(equipment)} | "
        f"Vaos: {len(spans)} | Confianca: {payload.confidence_global:.2f}"
    )
    if corpus_case:
        text += f" | Gabarito de benchmark: caso {corpus_case}"
    c.drawString(x + 6, y + 8, text[:190])


def _best_project_page_index(payload: TechnicalPayload) -> int:
    for page in payload.pages:
        if page.kind == "PROJETO_REDE":
            return page.index
    for page in payload.pages:
        if page.orientation == "landscape":
            return page.index
    return 0


def _side_panel(c, payload: TechnicalPayload, x: float, y: float, w: float, h: float) -> None:
    from reportlab.lib import colors

    c.setFillColor(colors.HexColor("#F2F8FB"))
    c.setStrokeColor(colors.HexColor("#D5DDE3"))
    c.rect(x, y, w, h, fill=1, stroke=1)
    yy = y + h - 16
    c.setFillColor(colors.HexColor("#282B2E"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 8, yy, "Resumo tecnico")
    yy -= 16

    sections = [
        ("Equipamentos", [f"{e.type} {e.code} {e.node_id or 'revisar'}" for e in payload.active_equipment()[:10]]),
        ("Vaos", [f"{s.id} {s.length_m or '-'}m {s.cable or ''}" for s in payload.active_spans()[:10]]),
        (
            "Validacoes",
            [f"{v.severity.upper()} {v.code}: {v.message}" for v in payload.validations if v.severity in {"critical", "error", "warning"}][:12],
        ),
    ]
    for title, rows in sections:
        c.setFillColor(colors.HexColor("#282B2E"))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x + 8, yy, title)
        yy -= 10
        c.setFont("Helvetica", 6.2)
        c.setFillColor(colors.HexColor("#222222"))
        if not rows:
            c.drawString(x + 10, yy, "-")
            yy -= 9
        for row in rows:
            for line in _wrap(row, 46):
                if yy < y + 14:
                    return
                c.drawString(x + 10, yy, line)
                yy -= 8
        yy -= 6


def _footer(c, payload: TechnicalPayload, x: float, y: float, w: float, h: float) -> None:
    from reportlab.lib import colors

    c.setFillColor(colors.HexColor("#EAF7FC"))
    c.setStrokeColor(colors.HexColor("#8BCFEB"))
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#154760"))
    c.setFont("Helvetica", 7)
    text = (
        "Saida local revisavel. Simbologia heuristica ate fornecimento de documentacao oficial JOBEL/RGE/CPFL. "
        f"Job {payload.job_id or '-'}."
    )
    c.drawString(x + 6, y + h / 2 - 2, text[:180])


def _symbol_legend_page(c, width: float, height: float, margin: float, logo_path: Path | None) -> None:
    from reportlab.lib import colors

    try:
        from croqui_engine.core.config import settings
        from croqui_engine.symbols.official_catalog import load_official_catalog

        catalog = load_official_catalog() if settings.use_official_catalog else None
    except Exception:
        catalog = None
    if not catalog:
        return

    c.showPage()
    c.setStrokeColor(colors.HexColor("#222222"))
    c.setLineWidth(0.8)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    y = height - margin - 22
    if logo_path and logo_path.exists() and logo_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        try:
            c.drawImage(str(logo_path), margin + 8, y - 24, width=96, height=42, preserveAspectRatio=True)
        except Exception:
            _jobel_wordmark(c, margin + 8, y - 10)
    else:
        _jobel_wordmark(c, margin + 8, y - 10)

    c.setFillColor(colors.HexColor("#172028"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin + 122, y, "Legenda e simbologia oficial importada")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#66737B"))
    c.drawString(margin + 122, y - 14, "Catalogo tecnico local para consulta e revisao.")
    c.setStrokeColor(colors.HexColor("#0CA2F8"))
    c.setLineWidth(2)
    c.line(margin, y - 34, width - margin, y - 34)

    y -= 58
    c.setFillColor(colors.HexColor("#172028"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 8, y, "Simbolos")
    y -= 16
    for symbol in catalog.get("symbols", [])[:16]:
        if y < margin + 72:
            break
        c.setFillColor(colors.HexColor("#F2F8FB"))
        c.setStrokeColor(colors.HexColor("#D5DDE3"))
        c.rect(margin + 8, y - 10, 18, 18, fill=1, stroke=1)
        _draw_symbol_sample(c, symbol.get("id", ""), margin + 17, y - 1)
        c.setFillColor(colors.HexColor("#172028"))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin + 34, y, symbol.get("id", "-")[:28])
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#34444D"))
        names = ", ".join(symbol.get("names", [])[:4])
        c.drawString(margin + 150, y, names[:110])
        y -= 22

    y -= 6
    c.setFillColor(colors.HexColor("#172028"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 8, y, "Estilos de linha e materiais")
    y -= 16
    rows = []
    rows.extend(item.get("description", "") for item in catalog.get("line_styles", [])[:10])
    rows.extend(f"Material {item.get('code', '')}" for item in catalog.get("materials", [])[:10])
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#34444D"))
    for row in rows[:18]:
        if y < margin + 20:
            break
        c.drawString(margin + 14, y, f"- {row[:150]}")
        y -= 10


def _draw_symbol_sample(c, symbol_id: str, x: float, y: float) -> None:
    from reportlab.lib import colors

    c.setStrokeColor(colors.HexColor("#172028"))
    c.setFillColor(colors.white)
    c.setLineWidth(1)
    if symbol_id == "POSTE":
        c.circle(x, y, 4, fill=0, stroke=1)
    elif symbol_id in {"TRANSFORMADOR", "TR"}:
        c.circle(x - 3, y, 4, fill=0, stroke=1)
        c.circle(x + 3, y, 4, fill=0, stroke=1)
    elif symbol_id in {"CHAVE_FUSIVEL", "FU", "CHAVE_COMANDO"}:
        c.line(x - 6, y - 4, x + 6, y + 4)
        c.circle(x - 6, y - 4, 1.5, fill=1, stroke=1)
        c.circle(x + 6, y + 4, 1.5, fill=1, stroke=1)
    elif symbol_id == "ATERRAMENTO":
        c.line(x, y + 5, x, y - 5)
        c.line(x - 5, y - 5, x + 5, y - 5)
        c.line(x - 3, y - 8, x + 3, y - 8)
    else:
        c.rect(x - 4, y - 4, 8, 8, fill=0, stroke=1)


def _scaled_positions(
    payload: TechnicalPayload,
    x: float,
    y: float,
    w: float,
    h: float,
    invert_y: bool = False,
) -> dict[str, tuple[float, float]]:
    nodes = payload.active_nodes()
    xs = [node.x if node.x is not None else idx * 120 for idx, node in enumerate(nodes)]
    ys = [node.y if node.y is not None else 0 for node in nodes]
    min_x, max_x = min(xs or [0]), max(xs or [1])
    min_y, max_y = min(ys or [0]), max(ys or [1])
    rw = max(max_x - min_x, 1)
    rh = max(max_y - min_y, 1)
    scale = min(w / rw, h / rh, 1.8)
    if len(nodes) == 1:
        return {nodes[0].id: (x + w / 2, y + h / 2)}
    positions = {}
    for idx, node in enumerate(nodes):
        nx = node.x if node.x is not None else idx * 120
        ny = node.y if node.y is not None else 0
        px = x + (nx - min_x) * scale + (w - rw * scale) / 2
        py_raw = y + (ny - min_y) * scale + (h - rh * scale) / 2
        py = y + h - (py_raw - y) if invert_y else py_raw
        positions[node.id] = (px, py)
    return positions


def _wrap(text: str, width: int) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def _eq_label(eq_type: str) -> str:
    mapping = {
        "TRANSFORMADOR": "TR",
        "CHAVE_FUSIVEL": "FU",
        "CHAVE_COMANDO": "FC",
    }
    return mapping.get(eq_type, eq_type[:3])
