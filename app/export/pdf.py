"""Writes the problem tree as a PDF with the same layout as the Word document (see word.py):
Current priorities, Humanitarian conditions, Impact, Shock and Context as stacked bands.

Uses reportlab (pure Python, nothing to install on the server) and bundles Liberation Sans, which has the
same widths as Arial and covers accented place names (Klaipėda, Şanlıurfa) that the built-in PDF fonts miss.
"""
import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from xml.sax.saxutils import escape

from ..tree.rules import kept_lines

HERE = os.path.dirname(__file__)
LOGO = os.path.join(HERE, "..", "static", "img", "ifrc-logo.png")
FONTS = os.path.join(HERE, "fonts")
INK, MUTED, GAP, RED, GRID = (colors.HexColor(c) for c in ("#333132", "#636163", "#8A4F00", "#F5333F", "#C9C9CC"))


def _register_fonts():
    if "PT-Regular" in pdfmetrics.getRegisteredFontNames():
        return
    for name, file in (("PT-Regular", "LiberationSans-Regular.ttf"), ("PT-Bold", "LiberationSans-Bold.ttf"),
                       ("PT-Italic", "LiberationSans-Italic.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(FONTS, file)))
    pdfmetrics.registerFontFamily("PT", normal="PT-Regular", bold="PT-Bold", italic="PT-Italic",
                                  boldItalic="PT-Bold")


def _styles():
    base = dict(fontName="PT-Regular", textColor=INK, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", fontName="PT-Bold", fontSize=15, leading=18, textColor=INK),
        "sub": ParagraphStyle("sub", **{**base, "textColor": MUTED}, fontSize=8, leading=10, spaceBefore=2),
        "band": ParagraphStyle("band", fontName="PT-Bold", fontSize=9.5, leading=12, textColor=colors.white),
        "box": ParagraphStyle("box", fontName="PT-Bold", fontSize=8.5, leading=10.5, textColor=INK, spaceAfter=2),
        "line": ParagraphStyle("line", **base, fontSize=8, leading=10, leftIndent=9, bulletIndent=1, spaceAfter=1),
        "gap": ParagraphStyle("gap", fontName="PT-Italic", fontSize=8, leading=10, textColor=GAP),
    }


class Arrow(Flowable):
    """The small upward triangle between bands (read the tree from the bottom up)."""
    def __init__(self, width):
        super().__init__()
        self.width, self.height = width, 9

    def draw(self):
        x, c = self.width / 2, self.canv
        c.setFillColor(colors.HexColor("#9A9A9E"))
        p = c.beginPath()
        p.moveTo(x - 3.5, 1.5); p.lineTo(x + 3.5, 1.5); p.lineTo(x, 7.5); p.close()
        c.drawPath(p, stroke=0, fill=1)


def _cell(box, st):
    out = [Paragraph(escape(box["title"]), st["box"])]
    lines = kept_lines(box)
    if not lines:
        out.append(Paragraph("To be completed", st["gap"]))
    out += [Paragraph(escape(t), st["line"], bulletText="•") for t in lines]
    return out


def _band(title, colour, boxes, width, st, layout=None):
    n = 2 if layout == "conditions" else len(boxes)
    head = [Paragraph(escape(title), st["band"])] + [""] * (n - 1)
    if layout == "conditions":
        data = [head, [_cell(boxes[0], st), _cell(boxes[1], st)], ["", _cell(boxes[2], st)]]
        spans = [("SPAN", (0, 1), (0, 2))]
    else:
        data = [head, [_cell(b, st) for b in boxes]]
        spans = []
    t = Table(data, colWidths=[width / n] * n)
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (n - 1, 0)), *spans,
        ("BACKGROUND", (0, 0), (n - 1, 0), colors.HexColor(colour)),
        ("GRID", (0, 1), (-1, -1), 0.6, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([t])


def build_pdf(view, meta, orientation="landscape"):
    """view: output of tree.rules.apply_edits. meta: dict with country, type_name, events, file, classification."""
    _register_fonts()
    st = _styles()
    size = landscape(A4) if orientation == "landscape" else portrait(A4)
    side, top = 1.3 * cm, 1.1 * cm
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=size, leftMargin=side, rightMargin=side, topMargin=top,
                            bottomMargin=top + 0.3 * cm, title=f"Problem tree: {meta['country']}",
                            author="Problem tree builder")
    width = size[0] - 2 * side

    left = [Paragraph(escape(f"{meta['country']}: {meta['type_name'].lower()}"), st["title"]),
            Paragraph(escape(f"Problem tree, draft. Based on {meta['events']} recorded events ({meta['file']})."),
                      st["sub"])]
    logo = Image(LOGO, width=0.75 * cm * 4.83, height=0.75 * cm) if os.path.exists(LOGO) else ""
    head = Table([[left, logo]], colWidths=[width - 5 * cm, 5 * cm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("LINEBELOW", (0, 0), (-1, 0), 2.2, RED), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))

    layers = {l["key"]: l for l in view["layers"]}
    impact_title = "Impact" + (f" – {view['impact_title']}" if view.get("impact_title") else "")
    shock_title = "Shock – " + view["shock_title"][:1].upper() + view["shock_title"][1:]
    story = [head, Spacer(1, 8)]
    bands = [("Current priorities", "priorities", None),
             ("Humanitarian conditions – expected consequences", "conditions", "conditions"),
             (impact_title, "impact", None), (shock_title, "shock", None), ("Context", "context", None)]
    for i, (title, key, layout) in enumerate(bands):
        if i:
            story.append(Arrow(width))
        story.append(_band(title, layers[key]["color"], layers[key]["boxes"], width, st, layout))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("PT-Regular", 7.5)
        canvas.setFillColor(colors.HexColor("#8C8C90"))
        canvas.drawCentredString(size[0] / 2, 0.7 * cm, meta.get("classification", "Internal"))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
