from __future__ import annotations

from pathlib import Path

from croqui_engine.core.config import settings


def generate_dependency_report(output_path: Path | None = None, logo_path: Path | None = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output_path = output_path or (settings.root_dir / "docs" / "JOBEL_DEPENDENCIAS_ENGINE_LOCAL.pdf")
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
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7, leading=9))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#531697")))
    story = []

    logo = Path(logo_path or settings.jobel_logo_path)
    if logo.exists() and logo.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        story.append(RLImage(str(logo), width=62 * mm, height=29 * mm))
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Dependencias Tecnicas para Consolidacao da Engine Local de Croquis", styles["Title"]))
    story.append(
        Paragraph(
            "JOBEL Croqui Engine - Extracao local, interpretacao tecnica e geracao automatizada de croquis RGE/CPFL",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 8 * mm))

    sections = [
        (
            "1. Sumario Executivo",
            "O projeto esta migrando para interpretacao local, reduzindo dependencia manual e eliminando envio de projetos para IA externa. A engine precisa de documentos oficiais e amostras homologadas para calibrar simbologia, regras de desenho e validacao. Sem esses insumos, o sistema opera em modo heuristico e exige revisao humana.",
        ),
        (
            "3. Base de Amostras para Treinamento Heuristico Local",
            "Solicitar minimo de 10 casos simples, 10 medios, 10 complexos, 5 com erro conhecido, 5 com alteracao de projeto e 5 com multiplas folhas. Para cada caso: PDF original, croqui esperado, observacoes do tecnico e validacao final.",
        ),
        (
            "4. Dependencias Funcionais da Aplicacao",
            "Definir perfis de usuario, fluxo de aprovacao, responsavel por gerar croqui final, necessidade de assinatura tecnica, retencao de arquivos, nomenclatura, auditoria, backup e guarda documental.",
        ),
        (
            "5. Seguranca e Confidencialidade",
            "Definir classificacao dos PDFs, politica de armazenamento local, restricao de envio externo, acesso por usuarios, logs, periodo de retencao, descarte seguro e anonimizacao quando possivel.",
        ),
        (
            "6. Criterios de Aceite Propostos",
            "Metas iniciais: metadados TES >= 95%, equipamentos principais >= 90%, vaos P/V >= 85%, associacao equipamento-poste >= 75%, croqui revisavel em 100% dos PDFs validos. Geracao automatica sem revisao somente apos homologacao.",
        ),
        (
            "7. Proximos Passos",
            "1. JOBEL fornece materiais obrigatorios. 2. Projeto incorpora simbologia oficial. 3. Engine e calibrada com amostras. 4. Tecnicos validam resultados. 5. Sistema entra em piloto controlado. 6. Homologacao define limites de uso automatico.",
        ),
    ]

    for title, body in sections[:1]:
        story.append(Paragraph(title, styles["Section"]))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 5 * mm))

    dependencies = [
        ("Excel original de croqui utilizado pela JOBEL", "Base real de layout e campos.", "Geracao Excel fica generica.", "Alta"),
        ("Aba de simbologia completa", "Mapear simbolos e materiais.", "Interpretacao permanece heuristica.", "Alta"),
        ("Template XLS oficial final", "Gerar saida compatibilizada.", "Excel simples sem layout oficial.", "Alta"),
        ("Manuais/GEDs/normas aplicaveis", "Validar regras tecnicas.", "Validacoes podem ser incompletas.", "Alta"),
        ("Criterios de linha, cor, tracejado e camada", "Diferenciar redes e estados.", "Croqui pode exigir correcao manual.", "Alta"),
        ("Criterios rede existente/nova/retirada/deslocada", "Inferir estados corretamente.", "Status fica indeterminado.", "Alta"),
        ("Lista oficial de materiais", "Normalizar codigos.", "Materiais ficam apenas extraidos.", "Media"),
        ("Lista oficial de equipamentos e nomenclaturas", "Classificar TR, FU, FC, RL etc.", "Tipos podem ser genericos.", "Alta"),
        ("Regras de avaliacao de viabilidade", "Preencher relatorio final.", "Tabela fica padrao.", "Media"),
        ("Regras de cabecalho e rodape", "Conformidade documental.", "PDF fica tecnico, nao oficial.", "Media"),
        ("Exemplos reais completos", "Calibrar e medir acuracia.", "Sem metricas confiaveis.", "Alta"),
        ("Amostras dificeis e excecoes", "Cobrir casos limite.", "Falhas podem aparecer no piloto.", "Alta"),
        ("Criterios de homologacao tecnica", "Definir quando aprovar.", "Aceite subjetivo.", "Alta"),
        ("Logo JOBEL em SVG/PNG", "Branding oficial.", "Uso de placeholder.", "Media"),
        ("Identidade visual desejada", "Ajustar UI corporativa.", "Visual permanece provisorio.", "Baixa"),
    ]
    story.append(Paragraph("2. Dependencias Obrigatorias", styles["Section"]))
    table_data = [["Item", "Dependencia", "Por que e necessaria", "Impacto se nao fornecida", "Prioridade"]]
    for idx, row in enumerate(dependencies, 1):
        table_data.append([str(idx), *row])
    table = Table(table_data, colWidths=[10 * mm, 38 * mm, 43 * mm, 43 * mm, 20 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#282B2E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B7C2CA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F8FB")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 5 * mm))

    for title, body in sections[1:]:
        story.append(Paragraph(title, styles["Section"]))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 4 * mm))

    doc.build(story)
    return output_path
