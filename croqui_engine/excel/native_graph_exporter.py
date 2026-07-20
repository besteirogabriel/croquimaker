from __future__ import annotations

import copy
import hashlib
import math
import posixpath
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from croqui_engine.core.config import settings
from croqui_engine.graph.croqui_graph import CroquiGraph, CroquiNode
from croqui_engine.office.libreoffice import convert_to_xlsx

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
EMU_PER_PIXEL = 9525

for prefix, uri in (("xdr", NS_DRAWING), ("a", NS_A), ("r", NS_REL)):
    ET.register_namespace(prefix, uri)

SYMBOL_NAMES = {
    "TR": "AutoShape 238",
    "FU": "Group 729",
    "FC": "Group 302",
    "RL": "Text Box 245",
    "RG": "Group 260",
    "OL": "Text Box 261",
    "SC": "Text Box 247",
}


class NativeExcelTemplateUnavailable(RuntimeError):
    pass


def export_native_graph_xlsx(
    graph: CroquiGraph,
    output_path: Path,
    template_path: Path | None = None,
) -> Path:
    """Export one editable DrawingML object per graph element.

    The official Croqui/Simbologia workbook remains the base. Symbols and line
    styles are cloned from its Simbologia drawing instead of being redrawn or
    flattened into a screenshot.
    """
    source = _select_template(graph, template_path)
    converted = _xlsx_template(source, output_path.parent)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_path = output_path.with_name(f".{output_path.name}.working")
    _rewrite_workbook(converted, work_path, graph)
    work_path.replace(output_path)
    _validate_headers(output_path, graph)
    return output_path


def _select_template(graph: CroquiGraph, template_path: Path | None) -> Path:
    configured = template_path or (
        Path(settings.excel_template_path) if settings.excel_template_path else None
    )
    if configured:
        configured = configured if configured.is_absolute() else settings.root_dir / configured
        if configured.is_file():
            return configured
    corpus = Path(settings.golden_corpus_path)
    if not corpus.is_absolute():
        corpus = settings.root_dir / corpus
    equipment_type = str(graph.mainEquipment.type or "").upper()
    candidates = sorted(corpus.rglob("*.xls")) if corpus.is_dir() else []
    matching = [
        item for item in candidates if f"croqui {equipment_type.lower()} " in item.name.lower()
    ]
    if matching:
        return matching[0]
    if candidates:
        return candidates[0]
    raise NativeExcelTemplateUnavailable(
        "Configure CROQUI_EXCEL_TEMPLATE_PATH com um XLS que contenha as abas Croqui e Simbologia."
    )


def _xlsx_template(source: Path, output_dir: Path) -> Path:
    del output_dir
    if source.suffix.lower() == ".xlsx":
        return source
    cache = settings.tmp_dir / "native_templates"
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:12]
    target = cache / f"{source.stem}-{digest}.xlsx"
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    conversion_dir = cache / digest
    converted = convert_to_xlsx(source, conversion_dir)
    if converted != target:
        shutil.copy2(converted, target)
    return target


def _rewrite_workbook(source: Path, output: Path, graph: CroquiGraph) -> None:
    with ZipFile(source) as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}

    workbook = ET.fromstring(parts["xl/workbook.xml"])
    workbook_rels = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    sheet_paths = _sheet_paths(workbook, workbook_rels)
    croqui_name = next((name for name in sheet_paths if "croqui" in _plain(name)), "")
    symbols_name = next((name for name in sheet_paths if "simbologia" in _plain(name)), "")
    if not croqui_name or not symbols_name:
        raise NativeExcelTemplateUnavailable(
            "O template precisa conter as abas Croqui e Simbologia."
        )

    croqui_sheet_path = sheet_paths[croqui_name]
    symbols_sheet_path = sheet_paths[symbols_name]
    croqui_sheet = ET.fromstring(parts[croqui_sheet_path])
    symbol_sheet = ET.fromstring(parts[symbols_sheet_path])
    croqui_drawing_path = _drawing_path(parts, croqui_sheet_path, croqui_sheet)
    symbol_drawing_path = _drawing_path(parts, symbols_sheet_path, symbol_sheet)
    croqui_drawing = ET.fromstring(parts[croqui_drawing_path])
    symbol_drawing = ET.fromstring(parts[symbol_drawing_path])

    _set_inline_cell(croqui_sheet, "I5", graph.header.departamento)
    _set_inline_cell(croqui_sheet, "AA5", graph.header.municipio.upper())
    _set_inline_cell(croqui_sheet, "AP5", graph.header.equipamento)
    _set_inline_cell(croqui_sheet, "I6", graph.header.data_levantamento)
    _set_inline_cell(croqui_sheet, "AH6", graph.header.responsavel)

    sources = _named_anchors(symbol_drawing)
    required_sources = {
        *(_symbol_name(node) for node in graph.nodes),
        *(
            source_name
            for edge in graph.edges
            for source_name in _edge_sources(edge.networkType, edge.style)
        ),
        *("Rectangle 334" for _ in graph.workZones),
    }
    missing_sources = sorted(source_name for source_name in required_sources if source_name not in sources)
    if missing_sources:
        raise NativeExcelTemplateUnavailable(
            "A aba Simbologia nao contem os objetos oficiais exigidos: "
            + ", ".join(missing_sources)
        )
    kept = [
        copy.deepcopy(anchor)
        for anchor in croqui_drawing
        if anchor.find(f"{{{NS_DRAWING}}}pic") is not None
    ]
    croqui_drawing[:] = kept
    next_id = max(_drawing_ids(croqui_drawing), default=0) + 1
    metrics = _SheetMetrics(croqui_sheet)
    mapper = _GraphMapper(metrics)

    for edge in graph.edges:
        source_node = _node(graph, edge.source)
        target_node = _node(graph, edge.target)
        if not source_node or not target_node:
            continue
        start = mapper.point(source_node.x, source_node.y)
        end = mapper.point(target_node.x, target_node.y)
        styles = _edge_sources(edge.networkType, edge.style)
        offsets = [0] if len(styles) == 1 else [-2 * EMU_PER_PIXEL, 2 * EMU_PER_PIXEL]
        for source_name, offset in zip(styles, offsets, strict=False):
            source_anchor = sources.get(source_name)
            if source_anchor is None:
                continue
            mid_x = (start[0] + end[0]) // 2
            segments = [
                ((start[0], start[1] + offset), (mid_x, start[1] + offset)),
                ((mid_x, start[1] + offset), (mid_x, end[1] + offset)),
                ((mid_x, end[1] + offset), (end[0], end[1] + offset)),
            ]
            for index, (point_a, point_b) in enumerate(segments):
                if point_a == point_b:
                    continue
                anchor = _line_anchor(source_anchor, point_a, point_b, metrics)
                next_id = _renumber(anchor, next_id, f"JOBEL-{edge.id}-{index + 1}")
                croqui_drawing.append(anchor)

    zone_source = sources.get("Rectangle 334")
    if zone_source is not None:
        for zone in graph.workZones:
            center = mapper.point(zone.x, zone.y)
            width = max(int(float(zone.width or 130) * mapper.scale_x), 30 * EMU_PER_PIXEL)
            height = max(int(float(zone.height or 76) * mapper.scale_y), 20 * EMU_PER_PIXEL)
            anchor = _simple_shape_anchor(zone_source, center, width, height, metrics)
            next_id = _renumber(anchor, next_id, f"JOBEL-{zone.id}")
            croqui_drawing.append(anchor)

    for node in graph.nodes:
        source_name = _symbol_name(node)
        source_anchor = sources.get(source_name)
        assert source_anchor is not None
        center = mapper.point(node.x, node.y)
        anchor = _translated_anchor(source_anchor, center, metrics)
        next_id = _renumber(anchor, next_id, f"JOBEL-{node.id}")
        croqui_drawing.append(anchor)
        label = next((item for item in graph.labels if item.attachedTo == node.id), None)
        text = str(label.text if label else node.code or "").strip()
        if text:
            label_anchor = _text_anchor(
                text, center[0] + 10 * EMU_PER_PIXEL, center[1] - 25 * EMU_PER_PIXEL, metrics
            )
            next_id = _renumber(label_anchor, next_id, f"JOBEL-LABEL-{node.id}")
            croqui_drawing.append(label_anchor)

    parts[croqui_sheet_path] = ET.tostring(croqui_sheet, encoding="utf-8", xml_declaration=True)
    parts[croqui_drawing_path] = ET.tostring(croqui_drawing, encoding="utf-8", xml_declaration=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)


def _sheet_paths(workbook: ET.Element, relationships: ET.Element) -> dict[str, str]:
    targets = {
        item.get("Id", ""): item.get("Target", "")
        for item in relationships.findall(f"{{{NS_PACKAGE_REL}}}Relationship")
    }
    result = {}
    for sheet in workbook.findall(f".//{{{NS_MAIN}}}sheet"):
        rel_id = sheet.get(f"{{{NS_REL}}}id", "")
        target = targets.get(rel_id, "")
        if target:
            result[sheet.get("name", "")] = posixpath.normpath(posixpath.join("xl", target))
    return result


def _drawing_path(parts: dict[str, bytes], sheet_path: str, sheet: ET.Element) -> str:
    drawing = sheet.find(f"{{{NS_MAIN}}}drawing")
    if drawing is None:
        raise NativeExcelTemplateUnavailable(
            f"A planilha {sheet_path} não possui objetos DrawingML."
        )
    rel_id = drawing.get(f"{{{NS_REL}}}id", "")
    rel_path = posixpath.join(
        posixpath.dirname(sheet_path), "_rels", f"{posixpath.basename(sheet_path)}.rels"
    )
    relationships = ET.fromstring(parts[rel_path])
    for item in relationships.findall(f"{{{NS_PACKAGE_REL}}}Relationship"):
        if item.get("Id") == rel_id:
            return posixpath.normpath(
                posixpath.join(posixpath.dirname(sheet_path), item.get("Target", ""))
            )
    raise NativeExcelTemplateUnavailable(f"Drawing não encontrado para {sheet_path}.")


def _named_anchors(drawing: ET.Element) -> dict[str, ET.Element]:
    result = {}
    for anchor in drawing:
        marker = anchor.find(f".//{{{NS_DRAWING}}}cNvPr")
        if marker is not None and marker.get("name"):
            result.setdefault(marker.get("name", ""), anchor)
    return result


def _translated_anchor(
    source: ET.Element, center: tuple[int, int], metrics: _SheetMetrics
) -> ET.Element:
    anchor = copy.deepcopy(source)
    offset, extent = _top_transform(anchor)
    old_x, old_y = int(offset.get("x", "0")), int(offset.get("y", "0"))
    width, height = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
    new_x, new_y = center[0] - width // 2, center[1] - height // 2
    _shift_transforms(anchor, new_x - old_x, new_y - old_y)
    _set_markers(anchor, (new_x, new_y), (new_x + width, new_y + height), metrics)
    return anchor


def _simple_shape_anchor(
    source: ET.Element,
    center: tuple[int, int],
    width: int,
    height: int,
    metrics: _SheetMetrics,
) -> ET.Element:
    anchor = copy.deepcopy(source)
    offset, extent = _top_transform(anchor)
    new_x, new_y = center[0] - width // 2, center[1] - height // 2
    offset.set("x", str(new_x))
    offset.set("y", str(new_y))
    extent.set("cx", str(width))
    extent.set("cy", str(height))
    _set_markers(anchor, (new_x, new_y), (new_x + width, new_y + height), metrics)
    return anchor


def _line_anchor(
    source: ET.Element,
    start: tuple[int, int],
    end: tuple[int, int],
    metrics: _SheetMetrics,
) -> ET.Element:
    anchor = copy.deepcopy(source)
    offset, extent = _top_transform(anchor)
    x0, y0 = min(start[0], end[0]), min(start[1], end[1])
    width, height = abs(end[0] - start[0]), abs(end[1] - start[1])
    offset.set("x", str(x0))
    offset.set("y", str(y0))
    extent.set("cx", str(width))
    extent.set("cy", str(height))
    xfrm = anchor.find(f".//{{{NS_A}}}xfrm")
    if xfrm is not None:
        if (end[0] - start[0]) * (end[1] - start[1]) < 0:
            xfrm.set("flipV", "1")
        else:
            xfrm.attrib.pop("flipV", None)
    _set_markers(anchor, (x0, y0), (x0 + max(width, 1), y0 + max(height, 1)), metrics)
    return anchor


def _text_anchor(text: str, x: int, y: int, metrics: _SheetMetrics) -> ET.Element:
    width, height = max(55, min(len(text) * 8, 160)) * EMU_PER_PIXEL, 19 * EMU_PER_PIXEL
    anchor = ET.Element(f"{{{NS_DRAWING}}}twoCellAnchor", {"editAs": "oneCell"})
    ET.SubElement(anchor, f"{{{NS_DRAWING}}}from")
    ET.SubElement(anchor, f"{{{NS_DRAWING}}}to")
    shape = ET.SubElement(anchor, f"{{{NS_DRAWING}}}sp")
    nv = ET.SubElement(shape, f"{{{NS_DRAWING}}}nvSpPr")
    ET.SubElement(nv, f"{{{NS_DRAWING}}}cNvPr", {"id": "0", "name": "JOBEL label"})
    ET.SubElement(nv, f"{{{NS_DRAWING}}}cNvSpPr", {"txBox": "1"})
    sp_pr = ET.SubElement(shape, f"{{{NS_DRAWING}}}spPr")
    xfrm = ET.SubElement(sp_pr, f"{{{NS_A}}}xfrm")
    ET.SubElement(xfrm, f"{{{NS_A}}}off", {"x": str(x), "y": str(y)})
    ET.SubElement(xfrm, f"{{{NS_A}}}ext", {"cx": str(width), "cy": str(height)})
    geom = ET.SubElement(sp_pr, f"{{{NS_A}}}prstGeom", {"prst": "rect"})
    ET.SubElement(geom, f"{{{NS_A}}}avLst")
    ET.SubElement(sp_pr, f"{{{NS_A}}}noFill")
    line = ET.SubElement(sp_pr, f"{{{NS_A}}}ln")
    ET.SubElement(line, f"{{{NS_A}}}noFill")
    body = ET.SubElement(shape, f"{{{NS_DRAWING}}}txBody")
    ET.SubElement(
        body,
        f"{{{NS_A}}}bodyPr",
        {"lIns": "0", "tIns": "0", "rIns": "0", "bIns": "0", "anchor": "ctr"},
    )
    paragraph = ET.SubElement(body, f"{{{NS_A}}}p")
    run = ET.SubElement(paragraph, f"{{{NS_A}}}r")
    run_pr = ET.SubElement(run, f"{{{NS_A}}}rPr", {"lang": "pt-BR", "sz": "900", "b": "0"})
    fill = ET.SubElement(run_pr, f"{{{NS_A}}}solidFill")
    ET.SubElement(fill, f"{{{NS_A}}}srgbClr", {"val": "000000"})
    ET.SubElement(run_pr, f"{{{NS_A}}}latin", {"typeface": "Arial"})
    ET.SubElement(run, f"{{{NS_A}}}t").text = text
    ET.SubElement(paragraph, f"{{{NS_A}}}endParaRPr", {"lang": "pt-BR", "sz": "900"})
    ET.SubElement(anchor, f"{{{NS_DRAWING}}}clientData")
    _set_markers(anchor, (x, y), (x + width, y + height), metrics)
    return anchor


def _top_transform(anchor: ET.Element) -> tuple[ET.Element, ET.Element]:
    child = next(
        (
            item
            for item in anchor
            if item.tag
            not in {f"{{{NS_DRAWING}}}from", f"{{{NS_DRAWING}}}to", f"{{{NS_DRAWING}}}clientData"}
        ),
        None,
    )
    if child is None:
        raise NativeExcelTemplateUnavailable("Objeto de simbologia sem geometria.")
    xfrm = child.find(f".//{{{NS_A}}}xfrm")
    if xfrm is None:
        raise NativeExcelTemplateUnavailable("Objeto de simbologia sem transformação.")
    offset = xfrm.find(f"{{{NS_A}}}off")
    extent = xfrm.find(f"{{{NS_A}}}ext")
    if offset is None or extent is None:
        raise NativeExcelTemplateUnavailable("Objeto de simbologia sem posição ou tamanho.")
    return offset, extent


def _shift_transforms(anchor: ET.Element, dx: int, dy: int) -> None:
    for tag in ("off", "chOff"):
        for item in anchor.findall(f".//{{{NS_A}}}{tag}"):
            item.set("x", str(int(item.get("x", "0")) + dx))
            item.set("y", str(int(item.get("y", "0")) + dy))


def _set_markers(
    anchor: ET.Element,
    start: tuple[int, int],
    end: tuple[int, int],
    metrics: _SheetMetrics,
) -> None:
    for name, point in (("from", start), ("to", end)):
        marker = anchor.find(f"{{{NS_DRAWING}}}{name}")
        if marker is None:
            marker = ET.Element(f"{{{NS_DRAWING}}}{name}")
            anchor.insert(0 if name == "from" else 1, marker)
        marker.clear()
        col, col_off = metrics.column_marker(point[0])
        row, row_off = metrics.row_marker(point[1])
        for key, value in (("col", col), ("colOff", col_off), ("row", row), ("rowOff", row_off)):
            ET.SubElement(marker, f"{{{NS_DRAWING}}}{key}").text = str(value)


def _renumber(anchor: ET.Element, next_id: int, name: str) -> int:
    for index, item in enumerate(anchor.findall(f".//{{{NS_DRAWING}}}cNvPr")):
        item.set("id", str(next_id))
        if index == 0:
            item.set("name", name[:250])
        next_id += 1
    return next_id


def _drawing_ids(drawing: ET.Element) -> list[int]:
    values = []
    for item in drawing.findall(f".//{{{NS_DRAWING}}}cNvPr"):
        try:
            values.append(int(item.get("id", "0")))
        except ValueError:
            continue
    return values


def _set_inline_cell(sheet: ET.Element, coordinate: str, value: str) -> None:
    cell = sheet.find(f".//{{{NS_MAIN}}}c[@r='{coordinate}']")
    if cell is None:
        row_number = int("".join(char for char in coordinate if char.isdigit()))
        row = sheet.find(f".//{{{NS_MAIN}}}row[@r='{row_number}']")
        if row is None:
            data = sheet.find(f"{{{NS_MAIN}}}sheetData")
            if data is None:
                raise NativeExcelTemplateUnavailable("Template sem sheetData.")
            row = ET.SubElement(data, f"{{{NS_MAIN}}}row", {"r": str(row_number)})
        cell = ET.SubElement(row, f"{{{NS_MAIN}}}c", {"r": coordinate})
    for child in list(cell):
        cell.remove(child)
    cell.set("t", "inlineStr")
    inline = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
    ET.SubElement(inline, f"{{{NS_MAIN}}}t").text = str(value or "")


def _validate_headers(path: Path, graph: CroquiGraph) -> None:
    with ZipFile(path) as workbook:
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    expected = {
        "I5": graph.header.departamento,
        "AA5": graph.header.municipio.upper(),
        "AP5": graph.header.equipamento,
    }
    for coordinate, value in expected.items():
        cell = sheet.find(f".//{{{NS_MAIN}}}c[@r='{coordinate}']")
        actual = "" if cell is None else "".join(cell.itertext())
        if actual != str(value or ""):
            raise RuntimeError(f"Falha ao validar o Excel: {coordinate} divergiu do grafo final.")


def _node(graph: CroquiGraph, node_id: str) -> CroquiNode | None:
    return next((item for item in graph.nodes if item.id == node_id), None)


def _symbol_name(node: CroquiNode) -> str:
    if node.kind in {"pole", "junction"}:
        return "Oval 148"
    equipment_type = str(node.equipmentType or ("TR" if node.kind == "transformer" else "")).upper()
    source_name = SYMBOL_NAMES.get(equipment_type)
    if source_name is None:
        raise NativeExcelTemplateUnavailable(
            f"Tipo de equipamento sem objeto oficial mapeado: {equipment_type or node.kind}."
        )
    return source_name


def _edge_sources(network_type: str, style: str) -> list[str]:
    if network_type == "AT_BT":
        return ["Line 429", "Line 430"]
    if network_type == "BT":
        return ["Line 429"]
    if style == "dashed" and network_type == "UNKNOWN":
        return ["Line 431"]
    return ["Line 430"]


def _plain(value: str) -> str:
    return value.lower().replace(" ", "_").replace("í", "i")


class _SheetMetrics:
    def __init__(self, sheet: ET.Element):
        self.column_widths = [64 * EMU_PER_PIXEL for _ in range(257)]
        for item in sheet.findall(f".//{{{NS_MAIN}}}col"):
            width = float(item.get("width", "9.14"))
            pixels = max(1, math.floor(width * 7 + 5))
            for index in range(int(item.get("min", "1")) - 1, int(item.get("max", "1"))):
                self.column_widths[index] = pixels * EMU_PER_PIXEL
        sheet_format = sheet.find(f"{{{NS_MAIN}}}sheetFormatPr")
        default_height = float(
            sheet_format.get("defaultRowHeight", "15") if sheet_format is not None else "15"
        )
        self.row_heights = [int(default_height * 12700) for _ in range(200)]
        for item in sheet.findall(f".//{{{NS_MAIN}}}row"):
            index = int(item.get("r", "1")) - 1
            self.row_heights[index] = int(float(item.get("ht", str(default_height))) * 12700)

    def column_start(self, index: int) -> int:
        return sum(self.column_widths[:index])

    def row_start(self, index: int) -> int:
        return sum(self.row_heights[:index])

    def column_marker(self, position: int) -> tuple[int, int]:
        return _marker(position, self.column_widths)

    def row_marker(self, position: int) -> tuple[int, int]:
        return _marker(position, self.row_heights)


class _GraphMapper:
    def __init__(self, metrics: _SheetMetrics):
        self.left = metrics.column_start(1)
        self.right = metrics.column_start(48)
        self.top = metrics.row_start(6)
        self.bottom = metrics.row_start(31)
        self.scale_x = (self.right - self.left) / (1084 - 36)
        self.scale_y = (self.bottom - self.top) / (594 - 112)

    def point(self, x: float | None, y: float | None) -> tuple[int, int]:
        px = float(x if x is not None else 560)
        py = float(y if y is not None else 350)
        return (
            int(self.left + (px - 36) * self.scale_x),
            int(self.top + (py - 112) * self.scale_y),
        )


def _marker(position: int, sizes: list[int]) -> tuple[int, int]:
    remaining = max(0, int(position))
    for index, size in enumerate(sizes):
        if remaining < size:
            return index, remaining
        remaining -= size
    return len(sizes) - 1, max(0, remaining)
