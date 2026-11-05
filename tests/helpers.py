import io
import os

from openpyxl import load_workbook

ROOT = os.path.dirname(os.path.dirname(__file__))
EXAMPLE = os.path.join(ROOT, "samples", "kyrgyzstan_example.xlsx")


def example_bytes():
    with open(EXAMPLE, "rb") as f:
        return f.read()


def modified_example(changes):
    """Return the example workbook with some cells changed. changes: {(row, header): value}."""
    wb = load_workbook(EXAMPLE)
    ws = wb["3. Hazard list"]
    headers = [c.value for c in ws[1]]
    for (row, header), value in changes.items():
        ws.cell(row=row, column=headers.index(header) + 1, value=value)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def generic_workbook(country, rows, areas=None):
    """A workbook made from the generic template (column "Areas"), with event rows and optionally
    an area list typed into tab Lists. rows: list of dicts keyed by tab 3 header."""
    from app.workbook.template import build_template
    wb = load_workbook(io.BytesIO(build_template(country)))
    ws = wb["3. Hazard list"]
    headers = [c.value for c in ws[1]]
    for i, values in enumerate(rows, 2):
        for header, value in values.items():
            ws.cell(row=i, column=headers.index(header) + 1, value=value)
    if areas:
        lst = wb["Lists"]
        col = [c.value for c in lst[1]].index("Areas") + 1
        for i, name in enumerate(areas, 3):     # row 2 holds National
            lst.cell(row=i, column=col, value=name)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def event(year, sub, areas, typ="Hydrological", **extra):
    return {"Year": year, "Start month": "Jun", "End month": "Jun", "Hazard type": typ, "Hazard sub-type": sub,
            "Areas": areas, "Description of hazard/shock": "Test event", "Sources": "Test", "Verified": "Yes",
            "Affected": 100, **extra}
