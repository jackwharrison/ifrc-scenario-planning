"""Reads tab 3 of the hazard workbook into a list of event dictionaries."""
import io

from openpyxl import load_workbook

from .columns import HAZARD_SHEET_HINT, NUMBER_FIELDS, columns_for


class ReadResult:
    def __init__(self, events=None, problem=None):
        self.events = events or []
        # problem is None when the file could be read, otherwise a dict describing why not
        self.problem = problem


def _clean_text(value):
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return "" if text in ("-", "\u00a0") else text


def _clean_number(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).replace(",", "").replace(" ", "")))
    except ValueError:
        return "invalid"


def read_workbook(data, area_column):
    """data: bytes of an .xlsx file. area_column: header of the area column for this country."""
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return ReadResult(problem={"kind": "broken"})

    sheet_name = next((n for n in wb.sheetnames if HAZARD_SHEET_HINT in n.lower()), None)
    if not sheet_name:
        return ReadResult(problem={"kind": "no_sheet", "sheets": wb.sheetnames})

    rows = list(wb[sheet_name].iter_rows(values_only=True))
    header_index = None
    for i, row in enumerate(rows[:20]):
        cells = [str(c).strip() if c is not None else "" for c in row]
        if "Year" in cells and "Hazard type" in cells:
            header_index = i
            break
    if header_index is None:
        return ReadResult(problem={"kind": "no_header", "sheet": sheet_name})

    header = [str(c).strip() if c is not None else "" for c in rows[header_index]]
    columns = columns_for(area_column)
    missing = [h for h, _ in columns if h not in header]
    data_rows = [r for r in rows[header_index + 1:] if any(c is not None and str(c).strip() for c in r)]
    if missing:
        return ReadResult(problem={"kind": "old_layout", "missing": missing,
                                   "rows": len(data_rows), "sheet": sheet_name})

    events = []
    for offset, row in enumerate(rows[header_index + 1:]):
        if not any(c is not None and str(c).strip() for c in row):
            continue
        event = {"_row": header_index + 2 + offset}
        for head, field in columns:
            value = row[header.index(head)] if header.index(head) < len(row) else None
            if field in NUMBER_FIELDS or field == "year":
                event[field] = _clean_number(value)
            else:
                event[field] = _clean_text(value)
        events.append(event)
    return ReadResult(events=events)
