"""Builds the blank hazard workbook for a country, with dropdowns taken from the shared lists.

Because the dropdowns come from the same lists the checks use, the template and the app never disagree.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .. import lists
from .columns import MONTHS, REQUIRED, columns_for

WIDTHS = {"year": 8, "start": 10, "end": 10, "type": 15, "sub": 24, "areas": 26, "desc": 50, "impact": 45,
          "sectors": 28, "factors": 36, "factorNotes": 40, "mitigating": 40, "sources": 40, "verified": 9}
ROWS = 500


def build_template(country):
    setup = lists.setup_for(country)
    area_column = setup["area_column"]
    area_names = lists.area_names(country)
    columns = columns_for(area_column)
    font = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    yellow = PatternFill("solid", fgColor="FFF4C2")

    wb = Workbook()
    readme = wb.active
    readme.title = "0. Read me first"
    lines = [
        (f"Hazard list template: {country}", Font(name="Arial", size=14, bold=True)), ("", font),
        ("How to fill in tab 3", bold),
        ("One row per significant event. Yellow columns are required; the rest make the problem tree richer.", font),
        ("Year: four digits, the year the event started.", font),
        ("Start month and End month: pick from the list. For an event running into the next year (Dec to Feb), "
         "the end month is simply earlier than the start month. Use Ongoing for events that have not ended.", font),
        ("Hazard type and sub-type: pick from the list (tab Lists).", font),
        (f"{area_column}, Sectors affected, Underlying factors (tags): one or more values from tab Lists, "
         f"separated by a semicolon, for example \"{'; '.join(area_names[:2]) or 'North; Capital'}\". "
         "Use National for country-wide events.", font),
        ((f"{area_column} in tab Lists: the first-level areas the app knows for {country}. If your National Society "
          "uses other names or another level, change the list there; the app reads it from the file you upload.")
         if area_names else
         (f"{area_column} in tab Lists: type your first-level areas (provinces, regions, districts...) once, "
          "one per row, before filling in tab 3. The app checks tab 3 against this list. If you leave it empty, "
          "the app uses the names typed in tab 3 and warns about spellings that look alike."), bold),
        ("Killed, Injured, Affected, Displaced, Houses damaged: whole numbers. Leave empty if unknown; "
         "enter 0 only if the source says none.", font),
        ("Verified: Yes once figures are checked against a primary source.", font), ("", font),
        ("Do not rename tabs, move the header row or change header names: the app reads them by name.", bold),
    ]
    for i, (text, f) in enumerate(lines, 1):
        cell = readme.cell(row=i, column=1, value=text)
        cell.font = f
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    readme.column_dimensions["A"].width = 120

    ws = wb.create_sheet("3. Hazard list")
    ws.append([h for h, _ in columns])
    for j, (head, field) in enumerate(columns, 1):
        c = ws.cell(row=1, column=j)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="F5333F")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = WIDTHS.get(field, 11)
        if field in REQUIRED:
            for r in range(2, 52):
                ws.cell(row=r, column=j).fill = yellow
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "C2"

    lst = wb.create_sheet("Lists")
    taxonomy = lists.hazard_types()
    subs = [s for v in taxonomy.values() for s in v]
    cols = [("Months", MONTHS + ["Ongoing"]), ("Hazard types", list(taxonomy)), ("Hazard sub-types", subs),
            (area_column, area_names + ["National"]), ("Sectors", lists.sectors()),
            ("Underlying factors", lists.factor_names()), ("Verified", ["Yes", "No"])]
    for j, (head, values) in enumerate(cols, 1):
        lst.cell(row=1, column=j, value=head).font = bold
        for i, v in enumerate(values, 2):
            lst.cell(row=i, column=j, value=v).font = font
        lst.column_dimensions[get_column_letter(j)].width = 32
        if head == area_column and not area_names:
            for i in range(len(values) + 2, len(values) + 42):    # space to type the areas, below National
                lst.cell(row=i, column=j).fill = yellow

    letter = {field: get_column_letter(j) for j, (_, field) in enumerate(columns, 1)}

    def dropdown(field, list_col, n, prompt):
        dv = DataValidation(type="list", formula1=f"=Lists!${list_col}$2:${list_col}${n + 1}", allow_blank=True)
        dv.error, dv.errorTitle, dv.prompt, dv.showInputMessage = "Pick a value from the list", "Not in list", prompt, True
        ws.add_data_validation(dv)
        dv.add(f"{letter[field]}2:{letter[field]}{ROWS}")

    dropdown("start", "A", 12, "Pick a month")
    dropdown("end", "A", 13, "Pick a month, or Ongoing")
    dropdown("type", "B", len(taxonomy), "Pick a hazard type")
    dropdown("sub", "C", len(subs), "Pick a sub-type")
    dropdown("verified", "G", 2, "Yes or No")
    for field in ("killed", "injured", "affected", "displaced", "houses"):
        dv = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
        dv.error = "Whole numbers only"
        ws.add_data_validation(dv)
        dv.add(f"{letter[field]}2:{letter[field]}{ROWS}")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
