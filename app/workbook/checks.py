"""Checks every row. Errors leave a row out of the tree; warnings are shown but do not block."""
import difflib
import re

from .. import lists
from .columns import MONTHS, NUMBER_FIELDS, split_list


def _key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def similar_area_names(names):
    """Groups of area names that are probably the same place spelled differently ("Jalal-Abad", "Jalalabad")."""
    groups, done = [], set()
    for a in names:
        if a in done:
            continue
        group = [b for b in names if b not in done and b != a and
                 (_key(a) == _key(b) or difflib.SequenceMatcher(None, _key(a), _key(b)).ratio() >= 0.85)]
        if group:
            group = [a] + group
            done.update(group)
            groups.append(group)
    return groups


def effective_lists(workbook_lists=None):
    """The app's default lists with the workbook's tab Lists laid over them. The workbook wins where both say
    something (for example which hazard type a sub-type belongs to)."""
    wl = workbook_lists or {}
    taxonomy = lists.hazard_types()
    types = list(taxonomy) + [t for t in wl.get("types", []) if t not in taxonomy]
    sub_types = {}
    for t, subs in taxonomy.items():
        for s in subs:
            sub_types.setdefault(s, set()).add(t)
    for s, t in (wl.get("subs") or {}).items():
        if t:
            sub_types[s] = {t}          # the workbook says where this sub-type belongs
        else:
            sub_types.setdefault(s, set())
    factors = {f["name"]: f["context"] for f in lists.factors()}
    factors.update({f: c for f, c in (wl.get("factors") or {}).items() if c})
    for f in (wl.get("factors") or {}):
        factors.setdefault(f, "Environmental and physical")
    sectors = list(dict.fromkeys(lists.sectors() + list(wl.get("sectors") or [])))
    return {"types": types, "sub_types": sub_types, "sectors": sectors, "factors": factors}


def check_events(events, country, areas=None, strict=True, subtypes=None, workbook_lists=None):
    """areas: the area names for this tree (default: the country's built-in list).
    strict: names outside the list are errors. With strict=False the list was taken from tab 3 itself,
    so names cannot be wrong, but near-duplicate spellings get a warning instead.
    workbook_lists: tab Lists of the uploaded workbook (reader.read_lists). Hazard types, sub-types, sectors and
    factors listed there are accepted like the app's own. Values in neither only get a warning: the row is used.
    subtypes: older way to pass the workbook's sub-types (names only)."""
    wl = dict(workbook_lists or {})
    if subtypes and not wl.get("subs"):
        wl["subs"] = {s: "" for s in subtypes}
    eff = effective_lists(wl)
    known_types, sub_types = eff["types"], eff["sub_types"]
    area_list = list(lists.area_names(country) if areas is None else areas)
    areas = area_list + ["National"]
    sector_names, factor_names = eff["sectors"], list(eff["factors"])
    groups = {}

    def add(key, level, title, fix, event):
        group = groups.setdefault(key, {"key": key, "level": level, "title": title, "fix": fix, "rows": []})
        group["rows"].append({"row": event["_row"], "year": event.get("year"),
                              "label": event.get("sub") or event.get("type") or "",
                              "areas": event.get("areas", "")})

    def maybe(value, options):
        close = difflib.get_close_matches(value, options, n=1, cutoff=0.8)
        return f"Did you mean {close[0]}? " if close else ""

    for e in events:
        year = e.get("year")
        if not isinstance(year, int) or not 1900 <= year <= 2100:
            add("year", "error", "Year is missing or not a four-digit year",
                "Enter the year the event started, for example 2024.", e)
        if e.get("start") not in MONTHS:
            add("start", "error", "Start month is missing or not from the list",
                "Pick a month from the dropdown (Jan to Dec).", e)
        if e.get("end") and e["end"] not in MONTHS and e["end"].lower() != "ongoing":
            add("end", "error", "End month is not from the list",
                "Pick a month from the dropdown, or Ongoing.", e)
        typ, sub = e.get("type"), e.get("sub")
        if not typ:
            add("type_missing", "error", "Hazard type is missing", "Pick a hazard type from tab Lists.", e)
        elif typ not in known_types:
            add("type_new", "warning", "New hazard type",
                maybe(typ, known_types) + "The row is used and counted under this type. Add it to the Hazard types "
                "column in tab Lists to stop this warning.", e)
        if not sub:
            add("sub_missing", "error", "Sub-type is missing",
                "Pick a sub-type from tab Lists, or add a new one at the bottom of its column.", e)
        elif typ and sub in sub_types and sub_types[sub] and typ not in sub_types[sub]:
            add("sub", "error", "Sub-type belongs to another hazard type",
                f"Tab Lists files {sub} under {', '.join(sorted(sub_types[sub]))}. Change the hazard type in the row, "
                "or change the type next to the sub-type in tab Lists.", e)
        elif sub not in sub_types:
            add("sub_new", "warning", "New hazard sub-type",
                maybe(sub, list(sub_types)) + "The row is used and the sub-type is counted as written. Add it to "
                "the Hazard sub-types column in tab Lists to stop this warning.", e)
        if strict and [a for a in split_list(e.get("areas")) if a not in areas]:
            add("area_bad", "error", "Area name not recognised",
                "Use the names in tab Lists, separated by semicolons.", e)
        if any(e.get(f) == "invalid" for f in NUMBER_FIELDS):
            add("number_bad", "error", "A figure is not a whole number",
                "Killed, injured, affected, displaced and houses damaged take whole numbers only.", e)

        if not split_list(e.get("areas")):
            add("area", "warning", "No area entered",
                "Add the areas affected, or National. Without it the event is left out of the area table and Geographical areas.", e)
        if not split_list(e.get("factors")):
            add("factors", "warning", "No underlying factors tagged",
                "Pick one or more tags. Without them the event is left out of the Context layer.", e)
        if all(e.get(f) in (None, "invalid") for f in NUMBER_FIELDS):
            add("figures", "warning", "No figures entered",
                "Add killed, affected, displaced or houses damaged if a source has them. Leave empty if truly unknown.", e)
        if e.get("killed") is None and re.search(r"killed|deaths?|died|fatalit", e.get("impact", ""), re.I):
            add("killed", "warning", "Impact notes mention deaths but Killed is empty",
                "Copy the death toll into the Killed column.", e)
        if str(e.get("verified", "")).lower() != "yes":
            add("verified", "warning", "Figures not verified",
                "Check against official or IFRC sources and set Verified to Yes.", e)
        if not e.get("sources"):
            add("sources", "warning", "No source",
                "Add at least one source. The tree shows sources for every figure.", e)
        unknown = [x for x in split_list(e.get("sectors")) if x not in sector_names]
        unknown += [x for x in split_list(e.get("factors")) if x not in factor_names]
        if unknown:
            add("tags", "warning", "Tag not in the list",
                "Use the wording in tab Lists so events can be counted together.", e)

    if not strict:
        for group in similar_area_names(area_list):
            counts = {a: sum(a in split_list(e.get("areas")) for e in events) for a in group}
            keep = max(group, key=lambda a: counts[a])
            for e in events:
                if any(a in split_list(e.get("areas")) for a in group if a != keep):
                    add("area_similar:" + keep, "warning", f"Area names that may be the same place: {', '.join(group)}",
                        f"Use one spelling, for example {keep}, so the events are counted together. "
                        "Listing the areas once in tab Lists prevents this.", e)

    error_rows = {r["row"] for g in groups.values() if g["level"] == "error" for r in g["rows"]}
    used = [e for e in events if e["_row"] not in error_rows]
    left_out = [e for e in events if e["_row"] in error_rows]
    issues = sorted(groups.values(), key=lambda g: (g["level"] != "error", -len(g["rows"])))
    return used, left_out, issues


def check_seasonal(seasonal):
    """Warnings for tabs 4 and 5. Nothing here blocks the tree; the seasonal calendar is shown as written."""
    groups = {}
    known = {s["no"] for s in seasonal.get("sources", [])}

    def add(key, title, fix, row):
        g = groups.setdefault(key, {"key": key, "level": "warning", "title": title, "fix": fix, "rows": []})
        g["rows"].append({"row": row["row"], "tab": "4", "year": None, "label": row["label"], "areas": ""})

    for r in seasonal.get("rows", []):
        if not r["months"]:
            add("cal_months", "Seasonal calendar: no months marked",
                "Put an x in the months this season covers (tab 4), or colour the cells.", r)
        if [n for n in r["sources"] if n not in known]:
            add("cal_sources", "Seasonal calendar: source number not in tab 5",
                "Use the numbers from the No. column of tab 5, separated by semicolons.", r)
        if not r["sources"]:
            add("cal_nosource", "Seasonal calendar: no source",
                "Add the numbers of one or more sources from tab 5, so readers can check the season.", r)
    return list(groups.values())

