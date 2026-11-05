"""Reads tab 3 of the hazard workbook into a list of event dictionaries."""
import io

from openpyxl import load_workbook

import re

from .columns import (CONTEXTS, HAZARD_SHEET_HINT, LIST_HEADERS, MONTHS, NUMBER_FIELDS, SEASONAL_HEADERS,
                      SEASONAL_SHEET_HINT, SOURCES_HEADERS, SOURCES_SHEET_HINT, columns_for)


GENERIC_AREA_COLUMN = "Areas"


class ReadResult:
    def __init__(self, events=None, problem=None, areas=None, subtypes=None, lists=None, seasonal=None):
        self.events = events or []
        # problem is None when the file could be read, otherwise a dict describing why not
        self.problem = problem
        # area names listed in tab Lists of the workbook (empty if that column is missing or empty)
        self.areas = areas or []
        # hazard sub-types listed in tab Lists, including any the National Society added
        self.subtypes = subtypes or []
        # everything else in tab Lists: see read_lists()
        self.lists = lists or {}
        # tabs 4 and 5: see read_seasonal()
        self.seasonal = seasonal or {"rows": [], "sources": []}


def _list_column(wb, header_name, skip=()):
    """The values under one header in tab Lists, in order, without blanks, duplicates or the values in skip."""
    name = next((n for n in wb.sheetnames if n.strip().lower() == "lists"), None)
    if not name:
        return []
    rows = list(wb[name].iter_rows(values_only=True))
    if not rows:
        return []
    header = [_clean_text(c) for c in rows[0]]
    if header_name not in header:
        return []
    j = header.index(header_name)
    seen, values = set(), []
    for row in rows[1:]:
        value = _clean_text(row[j]) if j < len(row) else ""
        if value and value.lower() not in skip and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _list_pairs(wb, header_name, partner_name):
    """(value, partner) pairs from two columns of tab Lists, for example a sub-type and its hazard type.
    The partner is "" when the column is missing or the cell is empty (older templates)."""
    name = next((n for n in wb.sheetnames if n.strip().lower() == "lists"), None)
    if not name:
        return []
    rows = list(wb[name].iter_rows(values_only=True))
    if not rows:
        return []
    header = [_clean_text(c) for c in rows[0]]
    if header_name not in header:
        return []
    j = header.index(header_name)
    k = header.index(partner_name) if partner_name in header else None
    seen, pairs = set(), []
    for row in rows[1:]:
        value = _clean_text(row[j]) if j < len(row) else ""
        partner = _clean_text(row[k]) if k is not None and k < len(row) else ""
        if value and value not in seen:
            seen.add(value)
            pairs.append((value, partner))
    return pairs


def read_lists(wb):
    """The lists a National Society can change in tab Lists. Anything missing simply falls back to the app's
    defaults, so older workbooks keep working.
    types: hazard types; subs: {sub-type: its hazard type, or ""}; sectors; factors: {factor: Context heading, or ""}."""
    contexts = {c.lower(): c for c in CONTEXTS}
    return {
        "types": _list_column(wb, LIST_HEADERS["types"]),
        "subs": dict(_list_pairs(wb, LIST_HEADERS["subs"], LIST_HEADERS["sub_type"])),
        "sectors": _list_column(wb, LIST_HEADERS["sectors"]),
        "factors": {f: contexts.get(c.lower(), "") for f, c in
                    _list_pairs(wb, LIST_HEADERS["factors"], LIST_HEADERS["factor_context"])},
    }


def _marked(cell):
    """A month counts as covered when it holds a value (x, 1, yes...) or is filled with a colour."""
    v = cell.value
    if v is not None and str(v).strip() and str(v).strip().lower() not in ("0", "no", "-", "false"):
        return True
    fill = getattr(cell, "fill", None)
    if fill is None or fill.fill_type != "solid":
        return False
    colour = fill.fgColor
    if colour.type == "rgb":
        return str(colour.rgb or "").upper()[-6:] not in ("FFFFFF", "000000", "")
    if colour.type == "theme":
        return colour.theme not in (0,)      # theme 0 is the white background
    return True


def _sheet(wb, hint):
    return next((n for n in wb.sheetnames if hint in n.lower()), None)


def read_seasonal(wb):
    """Tab 4 (seasonal calendar) and tab 5 (sources). Both are optional.

    rows: [{label, category, months: [0-11], notes, sources: [numbers], row}]
    sources: [{no, group, title, links: [url, ...]}]  (a Link cell may hold several links)
    """
    out = {"rows": [], "sources": []}
    name = _sheet(wb, SOURCES_SHEET_HINT)
    if name and SEASONAL_SHEET_HINT not in name.lower():
        rows = list(wb[name].iter_rows(values_only=True))
        hi = next((i for i, r in enumerate(rows[:10]) if SOURCES_HEADERS["title"] in [_clean_text(c) for c in r]), None)
        if hi is not None:
            head = [_clean_text(c) for c in rows[hi]]
            col = {k: head.index(h) if h in head else None for k, h in SOURCES_HEADERS.items()}
            get = lambda r, k: _clean_text(r[col[k]]) if col[k] is not None and col[k] < len(r) else ""
            for r in rows[hi + 1:]:
                title = get(r, "title")
                if not title:
                    continue
                no = re.match(r"\d+", get(r, "no") or "")
                out["sources"].append({"no": int(no.group()) if no else len(out["sources"]) + 1,
                                       "group": get(r, "group"), "title": title,
                                       "links": re.findall(r"https?://[^\s;,]+", get(r, "link"))})
    name = _sheet(wb, SEASONAL_SHEET_HINT)
    if not name:
        return out
    ws = wb[name]
    rows = list(ws.iter_rows())
    hi = next((i for i, r in enumerate(rows[:10]) if {"Jan", "Dec"} <= {_clean_text(c.value) for c in r}), None)
    if hi is None:
        return out
    head = [_clean_text(c.value) for c in rows[hi]]
    month_col = [head.index(m) for m in MONTHS]
    find = lambda key, starts=False: next((j for j, h in enumerate(head)
                                           if h == SEASONAL_HEADERS[key] or (starts and h.startswith(SEASONAL_HEADERS[key].split(" ")[0]))), None)
    c_label = find("label")
    if c_label is None:
        c_label = 0
    c_cat, c_notes, c_src = find("category"), find("notes"), find("sources", starts=True)
    cell = lambda r, j: r[j] if j is not None and j < len(r) else None
    text = lambda r, j: _clean_text(cell(r, j).value) if cell(r, j) is not None else ""
    for i, r in enumerate(rows[hi + 1:], start=hi + 2):
        label = text(r, c_label)
        if not label:
            continue
        months = [m for m, j in enumerate(month_col) if cell(r, j) is not None and _marked(cell(r, j))]
        out["rows"].append({"label": label, "category": text(r, c_cat), "months": months, "notes": text(r, c_notes),
                            "sources": [int(x) for x in re.findall(r"\d+", text(r, c_src))], "row": i})
    return out


def _list_areas(wb, area_column):
    """Area names from tab Lists: the column headed like the area column in tab 3. National is left out."""
    return _list_column(wb, area_column, skip=("national",))


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
    """data: bytes of an .xlsx file. area_column: header of the area column for this country.

    A workbook made from the generic template (column "Areas") is accepted for every country.
    """
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
    if area_column not in header:
        # Accept any template: the generic one ("Areas"), or one made for another set-up ("Wilayas", "Regions"...),
        # recognised by its place right after "Hazard sub-type".
        if GENERIC_AREA_COLUMN in header:
            area_column = GENERIC_AREA_COLUMN
        elif "Hazard sub-type" in header and header.index("Hazard sub-type") + 1 < len(header):
            candidate = header[header.index("Hazard sub-type") + 1]
            if candidate and candidate not in {h for h, _ in columns_for("")}:
                area_column = candidate
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
    found = read_lists(wb)
    return ReadResult(events=events, areas=_list_areas(wb, area_column), subtypes=list(found["subs"]), lists=found,
                      seasonal=read_seasonal(wb))
