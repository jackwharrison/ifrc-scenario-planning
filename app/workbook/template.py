"""Builds the blank hazard workbook for a country.

Tab Lists is filled with the app's default lists (app/lists/*.yaml) and left open for the National Society to
extend. The app reads tab Lists back from every uploaded workbook, so a new hazard, sector or factor only needs
typing in the spreadsheet.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .. import lists
from .columns import (CALENDAR_CATEGORIES, CONTEXTS, LIST_HEADERS, LIST_HEADERS_CALENDAR, MONTHS, REQUIRED,
                      SEASONAL_HEADERS, SOURCES_HEADERS, columns_for)

WIDTHS = {"year": 8, "start": 10, "end": 10, "type": 15, "sub": 24, "areas": 26, "desc": 50, "impact": 45,
          "sectors": 28, "factors": 36, "factorNotes": 40, "mitigating": 40, "sources": 40, "verified": 9}
ROWS = 500
SPARE = 40      # empty rows left under each editable list in tab Lists


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
        ("Tab Lists is yours to change. Every list there feeds the dropdowns in tab 3 and is read by the app when "
         "you upload, so nothing has to change in the app itself:", bold),
        ("- Add a hazard type, sub-type, sector or underlying factor by typing it in an empty yellow cell at the "
         "bottom of its column. It appears in the dropdowns straight away.", font),
        ("- For a new sub-type, also say which hazard type it belongs to (next column). For a new underlying factor, "
         "say which Context heading it goes under: Political, Economic, Socio-cultural, Security, or Environmental "
         "and physical.", font),
        ((f"- {area_column}: the first-level areas the app knows for {country}. If your National Society uses other "
          "names or another level, change the list.") if area_names else
         (f"- {area_column}: type your first-level areas (provinces, regions, districts...) once, one per row, "
          "before filling in tab 3. If you leave it empty, the app uses the names typed in tab 3 and warns about "
          "spellings that look alike."), font),
        ("", font),
        ("Tab 4, Seasonal calendar (optional)", bold),
        ("One row per season or recurring risk: winter, snowmelt floods, planting, harvest, transhumance, heating season, "
         "measles season... Put an x in each month it covers (or colour the cells), pick a Category for its colour, and "
         "give the numbers of its sources from tab 5. The app shows it as a colour-coded calendar on the Review tree "
         "page, with the sources one click away.", font),
        ("Tab 5, Sources (optional)", bold),
        ("One row per source: a number, a group (for example Disaster seasons, Agriculture, Energy, Health), the title "
         "and the link. Tab 4 refers to these numbers.", font),
        ("", font),
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

    # Tab Lists. Editable lists get SPARE empty yellow rows; the dropdowns in tab 3 reach into them, so anything
    # typed there can be picked straight away. The reader takes all of these back from the uploaded file.
    lst = wb.create_sheet("Lists")
    taxonomy = lists.hazard_types()
    sub_pairs = [(s, t) for t, subs_ in taxonomy.items() for s in subs_]
    factor_pairs = [(f["name"], f["context"]) for f in lists.factors()]
    cols = [  # (header, values, editable)
        ("Months", MONTHS + ["Ongoing"], False),
        (LIST_HEADERS["types"], list(taxonomy), True),
        (LIST_HEADERS["subs"], [s for s, _ in sub_pairs], True),
        (LIST_HEADERS["sub_type"], [t for _, t in sub_pairs], True),
        (area_column, area_names + ["National"], not area_names),
        (LIST_HEADERS["sectors"], lists.sectors(), True),
        (LIST_HEADERS["factors"], [f for f, _ in factor_pairs], True),
        (LIST_HEADERS["factor_context"], [c for _, c in factor_pairs], True),
        ("Verified", ["Yes", "No"], False),
        (LIST_HEADERS_CALENDAR, CALENDAR_CATEGORIES, True),
        (LIST_HEADERS["contexts"], list(CONTEXTS), False),
    ]
    col_of, size = {}, {}
    for j, (head, values, editable) in enumerate(cols, 1):
        col_of[head], size[head] = get_column_letter(j), len(values) + (SPARE if editable else 0)
        lst.cell(row=1, column=j, value=head).font = bold
        for i, v in enumerate(values, 2):
            lst.cell(row=i, column=j, value=v).font = font
        lst.column_dimensions[get_column_letter(j)].width = 30
        if editable:
            for i in range(len(values) + 2, len(values) + 2 + SPARE):
                lst.cell(row=i, column=j).fill = yellow
    lst.freeze_panes = "A2"

    def ref(head):
        return f"=Lists!${col_of[head]}$2:${col_of[head]}${size[head] + 1}"

    def dropdown(sheet, cells, formula, prompt):
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.prompt, dv.showInputMessage = prompt, True     # no error box: new values can be typed in tab Lists
        sheet.add_data_validation(dv)
        dv.add(cells)

    letter = {field: get_column_letter(j) for j, (_, field) in enumerate(columns, 1)}
    col = lambda field: f"{letter[field]}2:{letter[field]}{ROWS}"
    dropdown(ws, col("start"), "=Lists!$A$2:$A$13", "Pick a month")
    dropdown(ws, col("end"), "=Lists!$A$2:$A$14", "Pick a month, or Ongoing")
    dropdown(ws, col("type"), ref(LIST_HEADERS["types"]), "Pick a hazard type")
    dropdown(ws, col("sub"), ref(LIST_HEADERS["subs"]), "Pick a sub-type, or add a new one in tab Lists")
    dropdown(ws, col("verified"), ref("Verified"), "Yes or No")
    # In tab Lists itself: the type of each sub-type, and the Context heading of each factor
    sub_type_col = col_of[LIST_HEADERS["sub_type"]]
    dropdown(lst, f"{sub_type_col}2:{sub_type_col}{size[LIST_HEADERS['sub_type']] + 1}", ref(LIST_HEADERS["types"]),
             "Which hazard type this sub-type belongs to")
    ctx_col = col_of[LIST_HEADERS["factor_context"]]
    dropdown(lst, f"{ctx_col}2:{ctx_col}{size[LIST_HEADERS['factor_context']] + 1}", ref(LIST_HEADERS["contexts"]),
             "Which Context heading this factor goes under")
    # Tab 4: seasonal calendar
    cal = wb.create_sheet("4. Seasonal calendar")
    cal_head = [SEASONAL_HEADERS["label"], SEASONAL_HEADERS["category"]] + MONTHS + [SEASONAL_HEADERS["sources"],
                                                                                   SEASONAL_HEADERS["notes"]]
    cal.append(cal_head)
    for j, head in enumerate(cal_head, 1):
        c = cal.cell(row=1, column=j)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="011E41")
        c.alignment = Alignment(horizontal="center" if head in MONTHS else "left", vertical="center", wrap_text=True)
        cal.column_dimensions[get_column_letter(j)].width = 5 if head in MONTHS else (36 if j == 1 else 20)
    cal.column_dimensions[get_column_letter(len(cal_head))].width = 50
    cal.freeze_panes = "C2"
    dropdown(cal, f"B2:B{SPARE * 2}", ref(LIST_HEADERS_CALENDAR), "Pick a category; it sets the colour")
    dropdown(cal, f"C2:{get_column_letter(2 + 12)}{SPARE * 2}", '"x"', "x if the season covers this month")

    # Tab 5: sources for the seasonal calendar
    src = wb.create_sheet("5. Sources")
    src_head = list(SOURCES_HEADERS.values())
    src.append(src_head)
    for j, (head, width) in enumerate(zip(src_head, (6, 22, 70, 60)), 1):
        c = src.cell(row=1, column=j)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="011E41")
        src.column_dimensions[get_column_letter(j)].width = width
    for i in range(2, SPARE + 2):
        src.cell(row=i, column=1, value=i - 1).font = font
    src.freeze_panes = "A2"

    wb.move_sheet("Lists", offset=len(wb.sheetnames) - 1 - wb.sheetnames.index("Lists"))
    for field in ("killed", "injured", "affected", "displaced", "houses"):
        dv = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
        dv.error = "Whole numbers only"
        ws.add_data_validation(dv)
        dv.add(f"{letter[field]}2:{letter[field]}{ROWS}")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
