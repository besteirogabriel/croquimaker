from __future__ import annotations

from pathlib import Path


def build_simple_pdf(title: str, sections: list[tuple[str, list[str]]], output_path: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="JobelSection", parent=styles["Heading2"], textColor=colors.HexColor("#531697")))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]
    for heading, rows in sections:
        story.append(Paragraph(heading, styles["JobelSection"]))
        for row in rows:
            story.append(Paragraph(row.replace("&", "&amp;"), styles["Small"]))
        story.append(Spacer(1, 4 * mm))
    doc.build(story)
    return output_path

