"""Turns checked events and risk scores into the problem tree.

Every generated line keeps the rule that produced it and the workbook rows it is based on,
so a reader can always see where a number comes from.

Layout follows the problem tree format used for eastern DRC:
Priorities, Humanitarian conditions, Impact, Shock, Context (read from the bottom up).
"""
import re

from .. import lists
from ..workbook.columns import MONTHS, MONTHS_LONG, split_list

LAYERS = [
    ("priorities", "Priorities", "What to prepare for, and where", "#F5333F"),
    ("conditions", "Humanitarian conditions", "Expected consequences and capacities", "#C0672A"),
    ("impact", "Impact", "What past events did to people and systems", "#7A5BA6"),
    ("shock", "Shock", "Hazards, timing and scale", "#1E6091"),
    ("context", "Context", "Underlying vulnerabilities and drivers", "#011E41"),
]

BANDS = [(5, "Very low"), (10, "Low"), (15, "Medium"), (20, "High"), (25, "Very high")]
HIGH_RISK = 16
COLD_SEASON_SUBS = {"Cold wave", "Heavy snowfall", "Snow storm / blizzard", "Avalanche", "Energy crisis", "Frost"}


# ---------- small helpers ----------

def fmt(n):
    return f"{n:,}"


def plural(n, word, many=None):
    return f"{fmt(n)} {word if n == 1 else (many or word + 's')}"


def lc(text):
    """Lower-case the first letter, but leave acronyms such as COVID-19 alone."""
    return text[0].lower() + text[1:] if re.match(r"^[A-Z][a-z]", text) else text


def count_by(events, key):
    """Group events by one or more keys; largest group first, ties in order of first appearance."""
    groups = {}
    for e in events:
        keys = key(e)
        for k in (keys if isinstance(keys, list) else [keys]):
            if k:
                groups.setdefault(k, []).append(e)
    return sorted(groups.items(), key=lambda kv: -len(kv[1]))


def subs_text(events):
    return " and ".join(lc(s) for s, _ in count_by(events, lambda e: e["sub"])[:2])


def risk_band(score):
    if not score:
        return "Not scored"
    for limit, name in BANDS:
        if score <= limit:
            return name
    return "Very high"


def hazards_present(events):
    found = {}
    for e in events:
        k = f"{e['type']}|{e['sub']}"
        h = found.setdefault(k, {"key": k, "type": e["type"], "sub": e["sub"], "n": 0, "last": 0})
        h["n"] += 1
        h["last"] = max(h["last"], e["year"])
    return sorted(found.values(), key=lambda h: (h["type"], -h["n"]))


def _rows(events):
    return [{"row": e["_row"], "year": e["year"], "sub": e["sub"], "areas": e.get("areas", ""),
             "verified": str(e.get("verified", "")).lower() == "yes"} for e in events]


def line(lid, text, rule, events):
    return {"id": lid, "text": text, "rule": rule, "rows": _rows(events)}


def box(bid, title, kind, lines_, note="", **extra):
    return {"id": bid, "title": title, "kind": kind, "note": note, "lines": lines_, **extra}


# ---------- the tree ----------

def build_tree(events, scores, country):
    """events: checked events. scores: {"type|sub": {"l": int, "i": int}}."""
    E = events
    if not E:
        return None
    setup = lists.country_setup(country) or {}
    area_label = setup.get("area_label", "area")
    T = {}

    # SHOCK
    by_type = count_by(E, lambda e: e["type"])
    hz = []
    for t, l in by_type:
        top_sub, top_l = count_by(l, lambda e: e["sub"])[0]
        hz.append(line("t-" + t, f"{t}: {plural(len(l), 'event')} since {min(e['year'] for e in l)}, "
                       f"most often {lc(top_sub)} ({len(top_l)}).",
                       "Count of events by hazard type, with the most frequent sub-type.", l))

    season = []
    wet = [e for e in E if e["type"] == "Hydrological" or e["sub"] == "Landslide"]
    if len(wet) >= 3:
        m = [0] * 12
        for e in wet:
            m[MONTHS.index(e["start"])] += 1
        best, bi = 0, 0
        for i in range(12):
            s = sum(m[(i + k) % 12] for k in range(4))
            if s > best:
                best, bi = s, i
        in_window = [e for e in wet if (MONTHS.index(e["start"]) - bi) % 12 < 4]
        season.append(line("s-wet", f"{best} of {len(wet)} floods, mudflows and landslides started between "
                           f"{MONTHS_LONG[bi]} and {MONTHS_LONG[(bi + 3) % 12]}.",
                           "Busiest four-month window by start month, for hydrological events and landslides.", in_window))
    elif wet:
        season.append(line("s-wet-few", f"Only {plural(len(wet), 'flood, mudflow or landslide', 'floods, mudflows or landslides')} "
                           "recorded: too few to show a seasonal pattern.",
                           "Seasonal patterns are only shown from three events upwards.", wet))
    cold = [e for e in E if e["sub"] in COLD_SEASON_SUBS]
    if cold:
        in_winter = [e for e in cold if e["start"] in ("Oct", "Nov", "Dec", "Jan", "Feb", "Mar")]
        season.append(line("s-cold", f"{len(in_winter)} of {plural(len(cold), 'cold-season event')} (cold waves, heavy snow, "
                           "avalanches, energy crises) started between October and March.",
                           "Start months of cold-season hazard sub-types.", cold))

    big = sorted([e for e in E if max(e.get("affected") or 0, e.get("displaced") or 0) > 0],
                 key=lambda e: -max(e.get("affected") or 0, e.get("displaced") or 0))[:3]
    largest = []
    for e in big:
        displaced, affected = e.get("displaced") or 0, e.get("affected") or 0
        figure = f"{fmt(displaced)} displaced" if displaced and displaced >= affected else f"{fmt(affected)} affected"
        where = f" in {', '.join(split_list(e['areas']))}" if split_list(e.get("areas")) else ""
        killed = f", {fmt(e['killed'])} killed" if e.get("killed") else ""
        largest.append(line(f"b-{e['_row']}", f"{e['year']}, {lc(e['sub'])}{where}: {figure}{killed}.",
                            "Three largest events by people affected or displaced.", [e]))

    priority = []
    for h in hazards_present(E):
        s = scores.get(h["key"]) or {}
        if s.get("l") and s.get("i") and s["l"] * s["i"] >= HIGH_RISK:
            priority.append({**h, "l": s["l"], "i": s["i"], "r": s["l"] * s["i"]})
    priority.sort(key=lambda h: -h["r"])
    pri_lines = [line("p-" + h["sub"], f"{h['sub']}: risk {h['r']} ({risk_band(h['r'])}), likelihood {h['l']}, impact {h['i']}.",
                      f"Hazards with a risk score of {HIGH_RISK} or more, from the scoring step.",
                      [e for e in E if e["sub"] == h["sub"]]) for h in priority]
    T["shock"] = [
        box("hazards", "Priority hazards", "auto", pri_lines,
            "" if pri_lines else "No hazard scores High yet. Score the risks first.", needs_scores=not pri_lines),
        box("hz", "Hazards by type", "auto", hz),
        box("season", "Seasonality", "auto", season, chart=True),
        box("big", "Largest recorded events", "auto", largest),
    ]
    T["shock_title"] = (", ".join(lc(h["sub"]) for h in priority[:3]) if priority
                        else ", ".join(lc(t) for t, _ in by_type[:3]) + " hazards")

    # IMPACT
    people = []
    killed_events = [e for e in E if (e.get("killed") or 0) > 0]
    if killed_events:
        people.append(line("k", f"At least {fmt(sum(e['killed'] for e in killed_events))} people killed in "
                           f"{plural(len(killed_events), 'event')} with a recorded death toll.",
                           "Sum of the Killed column. Empty cells are not counted as zero.", killed_events))
        by_deaths = sorted(((t, l, sum(e["killed"] for e in l)) for t, l in count_by(killed_events, lambda e: e["type"])),
                           key=lambda x: -x[2])[0]
        worst = sorted(by_deaths[1], key=lambda e: -e["killed"])[:3]
        people.append(line("kt", f"{by_deaths[0]} events account for {fmt(by_deaths[2])} of these deaths, "
                           f"mostly from {subs_text(worst)}.", "Deaths grouped by hazard type.", by_deaths[1]))
    health = [e for e in E if "Health" in split_list(e.get("sectors"))]
    if health:
        people.append(line("hl", f"Health affected in {plural(len(health), 'event')}, most often by {subs_text(health)}.",
                           "Count of events tagged with the Health sector.", health))

    displacement = []
    disp = [e for e in E if (e.get("displaced") or 0) > 0]
    if disp:
        by_size = sorted(disp, key=lambda e: -e["displaced"])
        displacement.append(line("d", f"At least {fmt(sum(e['displaced'] for e in disp))} people displaced across "
                                 f"{plural(len(disp), 'event')}, mostly by {subs_text(by_size[:2])}.",
                                 "Sum of the Displaced column.", disp))
        top = by_size[0]
        where = f" in {', '.join(split_list(top['areas']))}" if split_list(top.get("areas")) else ""
        displacement.append(line("d1", f"Largest single displacement: {fmt(top['displaced'])} people, "
                                 f"{top['year']} {lc(top['sub'])}{where}.", "Event with the highest Displaced figure.", [top]))

    systems = []
    house_events = [e for e in E if (e.get("houses") or 0) > 0]
    if house_events:
        total = sum(e["houses"] for e in house_events)
        systems.append(line("h", f"At least {fmt(total)} houses damaged or destroyed across {plural(len(house_events), 'event')}.",
                            "Sum of the Houses damaged column.", house_events))
        sub, l, n = sorted(((s, l, sum(e["houses"] for e in l)) for s, l in count_by(house_events, lambda e: e["sub"])),
                           key=lambda x: -x[2])[0]
        systems.append(line("ht", f"{sub} events account for {fmt(n)} of them ({round(n / total * 100)}%).",
                            "Houses damaged grouped by sub-type.", l))
    other_sectors = count_by(E, lambda e: [s for s in split_list(e.get("sectors")) if s not in ("Health", "Transport", "Protection")])
    for s, l in other_sectors[:3]:
        systems.append(line("sec-" + s, f"{s} affected in {plural(len(l), 'event')}, most often by {subs_text(l)}.",
                            "Count of the Sectors affected tags.", l))

    access = []
    transport = [e for e in E if "Transport" in split_list(e.get("sectors"))]
    remote = [e for e in E if "Remote areas with single access road" in split_list(e.get("factors"))]
    if transport:
        access.append(line("tr", f"Roads or transport cut in {plural(len(transport), 'event')}, most often by {subs_text(transport)}.",
                           "Count of events tagged with the Transport sector.", transport))
    if remote:
        access.append(line("rem", f"Remote areas with a single access road listed as a factor in {plural(len(remote), 'event')}.",
                           "Count of the Remote areas factor tag.", remote))
    affected_events = [e for e in E if (e.get("affected") or 0) > 0]
    T["impact_title"] = (f"at least {fmt(sum(e['affected'] for e in affected_events))} people affected in recorded events"
                         if affected_events else "")
    T["impact"] = [
        box("disp", "On displacement", "auto", displacement),
        box("people", "On people", "auto", people),
        box("systems", "On systems and services", "auto", systems),
        box("access", "On humanitarian access", "mixed", access,
            "Counts come from the Transport tag and the remote-areas factor. Access constraints for responders need your input."),
    ]

    # CONTEXT: factor tags grouped by the context column set in factors.yaml
    factor_groups = count_by(E, lambda e: split_list(e.get("factors")))

    def factor_lines(category):
        return [line("f-" + f, f"{f}: listed for {plural(len(l), 'event')}, mostly {subs_text(l)}.",
                     f"Count of the Underlying factors tag, grouped under {category}.", l)
                for f, l in factor_groups if lists.factor_context(f) == category]

    def societal(subs, lid):
        l = [e for e in E if e["sub"] in subs]
        if not l:
            return []
        parts = ", ".join(f"{s} ({len(x)})" for s, x in count_by(l, lambda e: e["sub"]))
        return [line(lid, f"{parts} since {min(e['year'] for e in l)}.", "Count of Societal events by sub-type.", l)]

    T["context"] = [
        box("political", "Political", "mixed", societal({"Civil unrest", "Political instability"}, "pol-ev") + factor_lines("Political"),
            "Counts are automatic. Why these events happened, and what could trigger the next one, needs your analysis."),
        box("economic", "Economic", "mixed", societal({"Economic / financial shock", "Energy crisis"}, "eco-ev") + factor_lines("Economic"),
            "Factor counts are automatic. Poverty rates and other indicators need adding by hand."),
        box("socio", "Socio-cultural", "mixed", factor_lines("Socio-cultural"),
            "Factor counts are automatic. Social dynamics need your analysis."),
        box("security", "Security", "mixed",
            societal({"Border armed clashes", "Inter-ethnic violence", "International armed conflict"}, "sec-ev") + factor_lines("Security"),
            "Counts are automatic. The current security situation needs your analysis."),
        box("env", "Environmental and physical", "auto", factor_lines("Environmental and physical"),
            "Not in the DRC layout. Added because a hazard profile is driven mostly by these factors."),
    ]

    # CONDITIONS
    mitigated = sorted([e for e in E if e.get("mitigating")], key=lambda e: -e["year"])
    coping = [line(f"m-{e['_row']}", f"{e['year']}, {lc(e['sub'])}: {e['mitigating'].rstrip('.')}.",
                   "Copied from the Mitigating factors column, most recent first. Rewrite as general statements.", [e])
              for e in mitigated[:4]]
    T["conditions"] = [
        box("living", "Living standards", "manual", [],
            "Expected consequences for living standards if a priority hazard hits. Comes from the scenarios in the workbook."),
        box("capacity", "Coping mechanisms", "mixed", coping,
            f"Mitigating factors are recorded for {len(mitigated)} of {len(E)} events. Shown as raw material; "
            "turn them into statements about how people and authorities cope."),
        box("wellbeing", "Physical and mental well-being", "manual", [],
            "Expected health, nutrition and psychosocial consequences. Comes from the scenarios or health partners."),
    ]

    # PRIORITIES
    area_groups = count_by(E, lambda e: [a for a in split_list(e.get("areas")) if a != "National"])
    areas = [line("o-" + a, f"{a}: {plural(len(l), 'event')}, most often {subs_text(l)}.",
                  f"Count of events per {area_label}. National events are not counted here.", l)
             for a, l in area_groups[:4]]
    T["priorities"] = [
        box("areas", "Geographical areas", "auto", areas),
        box("groups", "Affected groups", "manual", [],
            "Who is most exposed: for example herders on summer pastures, households in mudflow paths, "
            "people relying on electric heating. Needs local knowledge."),
        box("sectors-pri", "Humanitarian sectors", "manual", [],
            "Decide once priority hazards and areas are agreed. The impact layer shows which sectors were hit most often."),
    ]
    return T


def apply_edits(tree, edits, left_out, manual):
    """Combine generated lines with the analyst's edits, left-out lines and hand-written lines."""
    layers = []
    for key, name, hint, color in LAYERS:
        boxes = []
        for b in tree[key]:
            lines_ = [{**l, "generated": l["text"], "text": edits.get(l["id"], l["text"]),
                       "edited": l["id"] in edits, "out": bool(left_out.get(l["id"]))} for l in b["lines"]]
            boxes.append({**b, "lines": lines_, "mine": manual.get(b["id"], [])})
        layers.append({"key": key, "name": name, "hint": hint, "color": color, "boxes": boxes})
    return {"layers": layers, "shock_title": tree["shock_title"], "impact_title": tree["impact_title"]}


def kept_lines(b):
    """Lines that go into the document: generated lines not left out, then hand-written lines."""
    return [l["text"] for l in b["lines"] if not l["out"]] + [m["text"] for m in b["mine"]]
