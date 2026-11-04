"""Checks every row. Errors leave a row out of the tree; warnings are shown but do not block."""
import re

from .. import lists
from .columns import MONTHS, NUMBER_FIELDS, split_list


def check_events(events, country):
    taxonomy = lists.hazard_types()
    all_subs = [s for subs in taxonomy.values() for s in subs]
    areas = lists.area_names(country) + ["National"]
    sector_names = lists.sectors()
    factor_names = lists.factor_names()
    groups = {}

    def add(key, level, title, fix, event):
        group = groups.setdefault(key, {"key": key, "level": level, "title": title, "fix": fix, "rows": []})
        group["rows"].append({"row": event["_row"], "year": event.get("year"),
                              "label": event.get("sub") or event.get("type") or "",
                              "areas": event.get("areas", "")})

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
        if e.get("type") not in taxonomy:
            add("type", "error", "Hazard type is not in the list",
                "Pick one of the hazard types in tab Lists.", e)
        elif e.get("sub") not in taxonomy[e["type"]]:
            fix = ("The sub-type exists, but under another hazard type. Change one of the two."
                   if e.get("sub") in all_subs else "Pick a sub-type from tab Lists.")
            add("sub", "error", "Sub-type does not belong to the hazard type", fix, e)
        if [a for a in split_list(e.get("areas")) if a not in areas]:
            add("area_bad", "error", "Area name not recognised",
                "Use the names in tab Lists, separated by semicolons.", e)
        if any(e.get(f) == "invalid" for f in NUMBER_FIELDS):
            add("number_bad", "error", "A figure is not a whole number",
                "Killed, injured, affected, displaced and houses damaged take whole numbers only.", e)

        if not split_list(e.get("areas")):
            add("area", "warning", "No area entered",
                "Add the areas affected, or National. Without it the event is left out of the map and Geographical areas.", e)
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

    error_rows = {r["row"] for g in groups.values() if g["level"] == "error" for r in g["rows"]}
    used = [e for e in events if e["_row"] not in error_rows]
    left_out = [e for e in events if e["_row"] in error_rows]
    issues = sorted(groups.values(), key=lambda g: (g["level"] != "error", -len(g["rows"])))
    return used, left_out, issues
