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
