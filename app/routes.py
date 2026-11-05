"""Pages: start, upload, check, score, tree (with the by-area table) and export."""
import datetime
import io
import os
import re

from flask import (Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file,
                   url_for)

from . import current_user, lists, storage
from .export.pdf import build_pdf
from .export.word import build_docx
from .tree.rules import BANDS, HIGH_RISK, apply_edits, build_tree, hazards_present, risk_band
from .workbook.checks import check_events, check_seasonal, effective_lists
from .workbook.columns import MONTHS, split_list
from .workbook.reader import read_workbook
from .workbook.template import build_template

bp = Blueprint("main", __name__)
SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")

# The app builds one kind of tree: a risk profile from past events and risk scores.
RISK_PROFILE = {
    "name": "Risk profile",
    "what": "You will build a risk profile from past events and risk scores. It stays current for about 12 months.",
    "needs": ["The hazard workbook with tab 3 filled in: one row for each significant event since about 2000.",
              "Someone to score likelihood and impact for the next 12 months, ideally with the National Society.",
              "People who can write the parts that can’t be counted: political and economic context, affected "
              "groups, expected consequences."],
    "note": "Few recorded events, as in many stable countries? The tree says where there are too few to show a "
            "pattern, and leans more on scenarios and context.",
}
STEPS = [("start", "Start"), ("upload", "Upload"), ("check", "Check"), ("scores", "Score risks"),
         ("tree", "Review tree"), ("export", "Export")]


def load(tree_id):
    tree = storage.get_tree(tree_id)
    if not tree:
        abort(404)
    setup = lists.setup_for(tree["country"])
    if tree["data"].get("area_label"):
        setup["area_label"] = tree["data"]["area_label"]
    tree["setup"] = setup
    tree["type"] = RISK_PROFILE
    return tree


def area_list(tree):
    """The areas this tree is counted against, and where the list came from (workbook, app or events)."""
    d = tree["data"]
    if d.get("areas"):
        return d["areas"], d.get("area_source", "workbook")
    return [a["name"] for a in tree["setup"].get("areas", [])], "app"


def clean_label(text):
    """The word for one area, as typed on the start page ("Province" becomes "province")."""
    text = re.sub(r"[^A-Za-zÀ-ÿ' -]", "", text or "").strip().lower()[:30]
    if len(text) > 4 and text.endswith("ies"):
        return text[:-3] + "y"
    return text[:-1] if len(text) > 3 and text.endswith("s") and not text.endswith(("ss", "us")) else text


def plural_word(word):
    """oblast -> oblasts, county -> counties."""
    if re.search(r"[^aeiou]y$", word):
        return word[:-1] + "ies"
    return word + "es" if re.search(r"(s|sh|ch|x|z)$", word) else word + "s"


def reached(tree):
    d = tree["data"]
    if d.get("events"):
        return 5
    if d.get("problem") or d.get("total") is not None:
        return 2
    return 1


def page(template, tree=None, step=None, **kw):
    uploads = storage.list_uploads(tree["id"]) if tree else []
    return render_template(template, tree=tree, step=step, steps=STEPS,
                           reached=reached(tree) if tree else 0, uploads=uploads, **kw)


def view_for(tree):
    d = tree["data"]
    t = build_tree(d.get("events", []), d.get("scores", {}), tree["country"], tree["setup"]["area_label"],
                   d.get("factor_contexts"))
    if not t:
        return None
    return apply_edits(t, d.get("edits", {}), d.get("out", {}), d.get("manual", {}))


# ---------- start ----------

@bp.get("/")
def home():
    return page("home.html", trees=storage.list_trees(), latest=storage.latest_uploads())


@bp.post("/trees/<int:tree_id>/delete")
def delete_tree(tree_id):
    tree = load(tree_id)
    storage.delete_tree(tree_id)
    return redirect(url_for("main.home", deleted=tree["country"]))


@bp.get("/trees/<int:tree_id>/uploads/<int:upload_id>")
def download_upload(tree_id, upload_id):
    """Download a workbook exactly as it was uploaded, so others can see what a tree was built from."""
    up = storage.get_upload(tree_id, upload_id)
    if not up:
        abort(404)
    return send_file(io.BytesIO(up["content"]), as_attachment=True, download_name=up["filename"],
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/start")
def start():
    return page("start.html", step=0, profile=RISK_PROFILE, countries=lists.countries(),
                ready=lists.ready_countries())


@bp.post("/start")
def start_post():
    country = request.form.get("country", "")
    if not lists.is_country(country):
        abort(400, "Choose a country from the list.")
    tree_id = storage.create_tree(country, "risk", current_user())
    label = clean_label(request.form.get("area_label"))
    if label and not lists.country_setup(country):
        storage.save_data(tree_id, {"area_label": label})
    return redirect(url_for("main.upload", tree_id=tree_id))


@bp.get("/trees/<int:tree_id>/start")
def tree_start(tree_id):
    """The Start step for a tree that already exists: shows its country and lets the area word be changed."""
    tree = load(tree_id)
    return page("start.html", tree, 0, profile=RISK_PROFILE, countries=[], ready=[])


@bp.post("/trees/<int:tree_id>/start")
def tree_start_post(tree_id):
    tree = load(tree_id)
    if not tree["setup"].get("prefilled"):
        data = tree["data"]
        label = clean_label(request.form.get("area_label"))
        if label:
            data["area_label"] = label
        else:
            data.pop("area_label", None)
        storage.save_data(tree_id, data)
    return redirect(url_for("main.upload", tree_id=tree_id))


@bp.get("/template/<country>.xlsx")
def template(country):
    if not lists.is_country(country):
        abort(404)
    return send_file(io.BytesIO(build_template(country)), as_attachment=True,
                     download_name=f"Hazard_list_template_{lists.slug(country)}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------- upload and check ----------

@bp.get("/trees/<int:tree_id>/upload")
def upload(tree_id):
    tree = load(tree_id)
    example = tree["setup"].get("example_workbook")
    has_example = bool(example) and os.path.exists(os.path.join(SAMPLES, example))
    return page("upload.html", tree, 1, has_example=has_example)


def _process(tree, filename, content):
    result = read_workbook(content, tree["setup"]["area_column"])
    data = tree["data"]
    for key in ("events", "left_out", "issues", "total", "problem", "areas", "area_source", "factor_contexts",
                "seasonal"):
        data.pop(key, None)
    data["file"] = filename
    if result.problem:
        data["problem"] = result.problem
    else:
        # Which areas to count against: the list in tab Lists of the workbook, else the list built into the
        # app for this country, else the names typed in tab 3 (checked for near-duplicate spellings).
        built_in = lists.area_names(tree["country"])
        if result.areas:
            areas, source = result.areas, "workbook"
        elif built_in:
            areas, source = built_in, "app"
        else:
            seen = []
            for e in result.events:
                seen += [a for a in split_list(e.get("areas")) if a.lower() != "national" and a not in seen]
            areas, source = seen, "events"
        used, left_out, issues = check_events(result.events, tree["country"], areas=areas, strict=source != "events",
                                              workbook_lists=result.lists)
        data.update(events=used, left_out=[e["_row"] for e in left_out], issues=issues, total=len(result.events),
                    areas=areas, area_source=source,
                    # which Context box each underlying factor goes in, including factors added in tab Lists
                    factor_contexts=effective_lists(result.lists)["factors"],
                    # tabs 4 and 5: the seasonal calendar and its sources
                    seasonal=result.seasonal)
        data["issues"] += check_seasonal(result.seasonal)
    storage.add_upload(tree["id"], filename, current_user(), content)
    storage.save_data(tree["id"], data)


@bp.post("/trees/<int:tree_id>/upload")
def upload_post(tree_id):
    tree = load(tree_id)
    f = request.files.get("workbook")
    if not f or not f.filename.lower().endswith((".xlsx", ".xlsm")):
        return page("upload.html", tree, 1, error="Choose an Excel file (.xlsx) to upload.", has_example=False), 400
    _process(tree, os.path.basename(f.filename), f.read())
    return redirect(url_for("main.check", tree_id=tree_id))


@bp.post("/trees/<int:tree_id>/use-example")
def use_example(tree_id):
    tree = load(tree_id)
    name = tree["setup"].get("example_workbook")
    if not name:
        abort(404)
    with open(os.path.join(SAMPLES, name), "rb") as fh:
        _process(tree, name, fh.read())
    return redirect(url_for("main.check", tree_id=tree_id))


@bp.get("/trees/<int:tree_id>/check")
def check(tree_id):
    tree = load(tree_id)
    d = tree["data"]
    warn_rows = {r["row"] for g in d.get("issues", []) if g["level"] == "warning" and not g["key"].startswith("cal_")
                 for r in g["rows"]}
    areas, source = area_list(tree)
    label = tree["setup"]["area_label"]
    return page("check.html", tree, 2, warn_rows=len(warn_rows), areas=areas, area_source=source,
                area_word=label if len(areas) == 1 else plural_word(label))


# ---------- scores ----------

@bp.route("/trees/<int:tree_id>/scores", methods=["GET", "POST"])
def scores(tree_id):
    tree = load(tree_id)
    events = tree["data"].get("events") or []
    if not events:
        return redirect(url_for("main.upload", tree_id=tree_id))
    hazards = hazards_present(events)
    if request.method == "POST":
        new = {}
        for h in hazards:
            l, i = request.form.get(f"l::{h['key']}"), request.form.get(f"i::{h['key']}")
            new[h["key"]] = {"l": int(l) if l and l.isdigit() else None, "i": int(i) if i and i.isdigit() else None}
        tree["data"]["scores"] = new
        storage.save_data(tree_id, tree["data"])
        return redirect(url_for("main.tree", tree_id=tree_id) if request.form.get("next") else
                        url_for("main.scores", tree_id=tree_id))
    sc = tree["data"].get("scores", {})
    for h in hazards:
        s = sc.get(h["key"]) or {}
        h["l"], h["i"] = s.get("l"), s.get("i")
        h["r"] = h["l"] * h["i"] if h["l"] and h["i"] else 0
        h["band"] = risk_band(h["r"])
    return page("scores.html", tree, 3, hazards=hazards, high=HIGH_RISK, bands=BANDS)


# ---------- tree ----------

def tree_payload(tree):
    events = tree["data"].get("events", [])
    return {
        "view": view_for(tree),
        "events": [{k: e.get(k) for k in ("_row", "year", "start", "end", "type", "sub", "areas", "killed", "affected",
                                          "displaced", "houses")} for e in events],
        "areas": area_list(tree)[0],
        "cities": [a["name"] for a in tree["setup"].get("areas", []) if a.get("city")],
        "seasonal": tree["data"].get("seasonal") or {"rows": [], "sources": []},
        "thisMonth": datetime.date.today().month - 1,
        "areaLabel": tree["setup"].get("area_label", "area"),
        "months": MONTHS,
        "editUrl": url_for("main.edit", tree_id=tree["id"]),
        "scoresUrl": url_for("main.scores", tree_id=tree["id"]),
    }


@bp.get("/trees/<int:tree_id>/tree")
def tree(tree_id):
    t = load(tree_id)
    if not t["data"].get("events"):
        return redirect(url_for("main.upload", tree_id=tree_id))
    return page("tree.html", t, 4, payload=tree_payload(t))


@bp.post("/trees/<int:tree_id>/edit")
def edit(tree_id):
    """Small JSON API used by the tree page: edit wording, leave out a line, add or remove a hand-written line."""
    t = load(tree_id)
    d = t["data"]
    body = request.get_json(silent=True) or {}
    action, line_id, box_id = body.get("action"), body.get("line"), body.get("box")
    text = (body.get("text") or "").strip()[:2000]
    edits, out, manual = d.setdefault("edits", {}), d.setdefault("out", {}), d.setdefault("manual", {})
    if action == "save" and line_id and text:
        edits[line_id] = text
    elif action == "reset" and line_id:
        edits.pop(line_id, None)
    elif action == "toggle" and line_id:
        out[line_id] = not out.get(line_id)
    elif action == "add" and box_id and text:
        mine = manual.setdefault(box_id, [])
        mine.append({"id": f"u{len(mine) + 1}-{os.urandom(3).hex()}", "text": text, "by": current_user()})
    elif action == "remove" and box_id:
        manual[box_id] = [m for m in manual.get(box_id, []) if m["id"] != body.get("id")]
    else:
        abort(400)
    storage.save_data(tree_id, d)
    return jsonify(tree_payload(load(tree_id)))


# ---------- export ----------

def _meta(t):
    d = t["data"]
    return {"country": t["country"], "type_name": t["type"]["name"], "events": len(d.get("events", [])),
            "file": d.get("file", ""), "classification": current_app.config["CLASSIFICATION"]}


@bp.get("/trees/<int:tree_id>/export")
def export(tree_id):
    t = load(tree_id)
    view = view_for(t)
    if not view:
        return redirect(url_for("main.upload", tree_id=tree_id))
    d = t["data"]
    hazards = hazards_present(d["events"])
    scored = sum(1 for h in hazards if (d.get("scores", {}).get(h["key"]) or {}).get("l")
                 and (d.get("scores", {}).get(h["key"]) or {}).get("i"))
    manual_empty = [b["title"] for l in view["layers"] for b in l["boxes"] if b["kind"] == "manual" and not b["mine"]]
    unverified = sum(1 for e in d["events"] if str(e.get("verified", "")).lower() != "yes")
    warn_rows = len({r["row"] for g in d.get("issues", []) if g["level"] == "warning"
                     and not g["key"].startswith("cal_") for r in g["rows"]})
    checks = [
        (scored == len(hazards), f"Risk scores: {scored} of {len(hazards)} hazards scored."),
        (not manual_empty, f"Boxes still to write: {', '.join(manual_empty)}." if manual_empty else "All analyst boxes have content."),
        (not unverified, f"{unverified} events with unverified figures feed the tree." if unverified else "All figures verified."),
        (not warn_rows, f"{warn_rows} rows had warnings at upload." if warn_rows else "No upload warnings."),
    ]
    return page("export.html", t, 5, view=view, meta=_meta(t), checks=checks, versions=storage.list_versions(tree_id))


EXPORT_FORMATS = {
    "docx": (build_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "pdf": (build_pdf, "application/pdf"),
}


@bp.get("/trees/<int:tree_id>/export.<fmt>")
def export_file(tree_id, fmt):
    """Download the tree as Word (.docx) or PDF, in landscape (default) or portrait: ?orientation=portrait."""
    if fmt not in EXPORT_FORMATS:
        abort(404)
    t = load(tree_id)
    view = view_for(t)
    if not view:
        abort(404)
    orientation = "portrait" if request.args.get("orientation") == "portrait" else "landscape"
    build, mimetype = EXPORT_FORMATS[fmt]
    data = build(view, _meta(t), orientation)
    name = f"Problem_tree_{lists.slug(t['country'])}{'_portrait' if orientation == 'portrait' else ''}.{fmt}"
    return send_file(io.BytesIO(data), as_attachment=True, download_name=name, mimetype=mimetype)


@bp.get("/trees/<int:tree_id>/download")
def export_download(tree_id):
    """Target of the form on the export page: ?fmt=docx|pdf&orientation=landscape|portrait."""
    fmt = request.args.get("fmt", "docx")
    return export_file(tree_id, fmt if fmt in EXPORT_FORMATS else "docx")


@bp.post("/trees/<int:tree_id>/versions")
def save_version(tree_id):
    t = load(tree_id)
    view = view_for(t)
    if view:
        storage.add_version(tree_id, current_user(), {"meta": _meta(t), "view": view, "scores": t["data"].get("scores", {})})
    return redirect(url_for("main.export", tree_id=tree_id, saved=1))
