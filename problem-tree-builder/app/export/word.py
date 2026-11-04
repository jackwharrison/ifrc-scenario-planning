"""Writes the problem tree as a one-page landscape Word document, laid out like the eastern DRC problem tree:
Current priorities, Humanitarian conditions, Impact, Shock and Context as stacked tables."""
import io
import os

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ..tree.rules import kept_lines

LOGO = os.path.join(os.path.dirname(__file__), "..", "static", "img", "ifrc-logo.png")
FONT = "Arial"
INK = RGBColor(0x33, 0x31, 0x32)
GAP_COLOUR = RGBColor(0x8A, 0x4F, 0x00)


def _shade(cell, hex_colour):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")      # 'clear' keeps the fill colour; 'solid' renders black
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_colour.lstrip("#"))
    tc_pr.append(shd)


def _cell_margins(table, top=60, bottom=80, side=100):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for edge, value in (("top", top), ("bottom", bottom), ("left", side), ("right", side)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def _para(container, text, size=8, bold=False, italic=False, colour=INK, style=None, align=None, space_after=1):
    p = container.add_paragraph(style=style) if style else container.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.font.name, run.font.size, run.font.bold, run.font.italic = FONT, Pt(size), bold, italic
    run.font.color.rgb = colour
    return p


def _fill_cell(cell, box):
    cell.paragraphs[0].text = ""
    first = cell.paragraphs[0]
    run = first.add_run(box["title"])
    run.font.name, run.font.size, run.font.bold = FONT, Pt(8.5), True
    run.font.color.rgb = INK
    first.paragraph_format.space_after = Pt(2)
    lines = kept_lines(box)
    if not lines:
        _para(cell, "To be completed", italic=True, colour=GAP_COLOUR)
    for text in lines:
        p = _para(cell, text, style="List Bullet")
        p.paragraph_format.left_indent = Cm(0.35)
        p.paragraph_format.first_line_indent = Cm(-0.3)


def _band(doc, title, colour, boxes, width_cm, layout=None):
    """One band: a coloured header row across all columns, then one cell per box."""
    n = 2 if layout == "conditions" else len(boxes)
    rows = 3 if layout == "conditions" else 2
    table = doc.add_table(rows=rows, cols=n)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _cell_margins(table)
    col_w = Cm(width_cm / n)
    for row in table.rows:
        for cell in row.cells:
            cell.width = col_w
    header = table.rows[0].cells[0].merge(table.rows[0].cells[n - 1])
    header.paragraphs[0].text = ""
    run = header.paragraphs[0].add_run(title)
    run.font.name, run.font.size, run.font.bold = FONT, Pt(9.5), True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    _shade(header, colour)
    for row in table.rows:   # keep each row on one page, and the header with its boxes
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
    for p in table.rows[0].cells[0].paragraphs:
        p.paragraph_format.keep_with_next = True
    if layout == "conditions":
        living = table.cell(1, 0).merge(table.cell(2, 0))
        _fill_cell(living, boxes[0])
        _fill_cell(table.cell(1, 1), boxes[1])
        _fill_cell(table.cell(2, 1), boxes[2])
    else:
        for i, b in enumerate(boxes):
            _fill_cell(table.cell(1, i), b)
    return table


def _arrow(doc):
    _para(doc, "▲", size=7, colour=RGBColor(0x9A, 0x9A, 0x9E), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)


def build_docx(view, meta):
    """view: output of tree.rules.apply_edits. meta: dict with country, type_name, events, file, classification."""
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin"):
        setattr(section, side, Cm(1.3))
    section.top_margin, section.bottom_margin = Cm(1.1), Cm(1.1)
    width = 29.7 - 2.6
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(8)

    head = doc.add_table(rows=1, cols=2)
    head.autofit = False
    head.cell(0, 0).width, head.cell(0, 1).width = Cm(width - 5), Cm(5)
    left = head.cell(0, 0)
    left.paragraphs[0].text = ""
    r = left.paragraphs[0].add_run(f"{meta['country']}: {meta['type_name'].lower()}")
    r.font.name, r.font.size, r.font.bold = FONT, Pt(15), True
    r.font.color.rgb = INK
    _para(left, f"Problem tree, draft. Based on {meta['events']} recorded events ({meta['file']}).", size=8,
          colour=RGBColor(0x63, 0x61, 0x63))
    right = head.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if os.path.exists(LOGO):
        right.add_run().add_picture(LOGO, height=Cm(0.75))
    rule = _para(doc, "", size=2, space_after=4)
    p_pr = rule._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "18"), ("space", "1"), ("color", "F5333F")):
        bottom.set(qn(f"w:{k}"), v)
    border.append(bottom)
    p_pr.append(border)

    layers = {l["key"]: l for l in view["layers"]}
    impact_title = "Impact" + (f" – {view['impact_title']}" if view.get("impact_title") else "")
    shock_title = "Shock – " + view["shock_title"][:1].upper() + view["shock_title"][1:]
    _band(doc, "Current priorities", layers["priorities"]["color"], layers["priorities"]["boxes"], width)
    _arrow(doc)
    _band(doc, "Humanitarian conditions – expected consequences", layers["conditions"]["color"],
          layers["conditions"]["boxes"], width, layout="conditions")
    _arrow(doc)
    _band(doc, impact_title, layers["impact"]["color"], layers["impact"]["boxes"], width)
    _arrow(doc)
    _band(doc, shock_title, layers["shock"]["color"], layers["shock"]["boxes"], width)
    _arrow(doc)
    _band(doc, "Context", layers["context"]["color"], layers["context"]["boxes"], width)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run(meta.get("classification", "Internal"))
    fr.font.name, fr.font.size = FONT, Pt(7.5)
    fr.font.color.rgb = RGBColor(0x8C, 0x8C, 0x90)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
