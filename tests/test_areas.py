"""Countries without a built-in area list: areas come from tab Lists of the workbook or from tab 3 itself."""
import io
import os
import re
import tempfile
import unittest

from openpyxl import load_workbook

from app import create_app, lists
from app.workbook.checks import check_events, similar_area_names
from app.workbook.reader import read_workbook
from app.workbook.template import build_template
from tests.helpers import event, generic_workbook

COUNTIES = ["Alytus", "Kaunas", "Klaipėda", "Vilnius"]


class GenericTemplateTests(unittest.TestCase):
    def test_country_without_setup_gets_generic_template(self):
        self.assertIsNone(lists.country_setup("Lithuania"))
        wb = load_workbook(io.BytesIO(build_template("Lithuania")))
        self.assertIn("Areas", [c.value for c in wb["3. Hazard list"][1]])
        self.assertIn("Areas", [c.value for c in wb["Lists"][1]])

    def test_reader_takes_areas_from_lists(self):
        data = generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas")], areas=COUNTIES)
        result = read_workbook(data, "Areas")
        self.assertIsNone(result.problem)
        self.assertEqual(result.areas, COUNTIES)          # National is left out

    def test_generic_workbook_accepted_for_country_with_setup(self):
        data = generic_workbook("Lithuania", [event(2020, "Flash flood", "Osh")])
        self.assertIsNone(read_workbook(data, "Oblasts").problem)


class AreaCheckTests(unittest.TestCase):
    def test_names_outside_workbook_list_are_errors(self):
        data = generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas"), event(2021, "Flash flood", "Kaunass")],
                                areas=COUNTIES)
        result = read_workbook(data, "Areas")
        used, left_out, issues = check_events(result.events, "Lithuania", areas=result.areas)
        self.assertEqual([e["_row"] for e in left_out], [3])
        self.assertIn("area_bad", {g["key"] for g in issues})

    def test_list_from_events_warns_about_lookalikes(self):
        names = ["Jalal-Abad", "Jalalabad", "Osh", "Naryn"]
        self.assertEqual(similar_area_names(names), [["Jalal-Abad", "Jalalabad"]])
        rows = [event(2020, "Flash flood", "Jalal-Abad"), event(2021, "Flash flood", "Jalal-Abad; Osh"),
                event(2022, "Flash flood", "Jalalabad")]
        result = read_workbook(generic_workbook("Lithuania", rows), "Areas")
        used, left_out, issues = check_events(result.events, "Lithuania", areas=["Jalal-Abad", "Osh", "Jalalabad"],
                                              strict=False)
        self.assertEqual(left_out, [])
        similar = next(g for g in issues if g["key"].startswith("area_similar"))
        self.assertEqual([r["row"] for r in similar["rows"]], [4])    # only the less common spelling


class GenericFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE_PATH": os.path.join(self.tmp.name, "t.db"),
                               "SESSION_COOKIE_SECURE": False})
        self.client = self.app.test_client()
        page = self.client.get("/start").get_data(as_text=True)
        self.csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, label="Counties"):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Lithuania",
                                             "area_label": label})
        self.assertEqual(r.status_code, 302)
        return r.headers["Location"].rsplit("/", 1)[0]

    def upload(self, url, data):
        r = self.client.post(url + "/upload", data={"csrf": self.csrf, "workbook": (io.BytesIO(data), "lt.xlsx")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)

    def test_unknown_country_refused(self):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Atlantis"})
        self.assertEqual(r.status_code, 400)

    def test_template_for_any_country(self):
        self.assertEqual(self.client.get("/template/Lithuania.xlsx").status_code, 200)
        self.assertEqual(self.client.get("/template/Atlantis.xlsx").status_code, 404)

    def test_areas_from_workbook_list(self):
        url = self.start()
        rows = [event(2020, "Flash flood", "Kaunas"), event(2021, "Flash flood", "Vilnius; Kaunas")]
        self.upload(url, generic_workbook("Lithuania", rows, areas=COUNTIES))
        check = self.client.get(url + "/check").get_data(as_text=True)
        self.assertIn("from tab Lists of this workbook", check)
        page = self.client.get(url + "/tree").get_data(as_text=True)
        self.assertIn('"areas": ["Alytus", "Kaunas", "Klaip', page)
        self.assertIn('"areaLabel": "county"', page)
        self.assertIn("By county", page)

    def test_areas_from_events_when_list_empty(self):
        url = self.start(label="")
        self.upload(url, generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas; National"),
                                                        event(2021, "Flash flood", "Utena")]))
        check = self.client.get(url + "/check").get_data(as_text=True)
        self.assertIn("taken from the names typed in tab 3", check)
        page = self.client.get(url + "/tree").get_data(as_text=True)
        self.assertIn('"areas": ["Kaunas", "Utena"]', page)
        self.assertIn('"areaLabel": "area"', page)



class SubtypeTests(unittest.TestCase):
    """Hazard sub-types are open: new ones are kept, and listing them in tab Lists removes the warning."""

    def test_new_subtype_is_kept_with_a_warning(self):
        data = generic_workbook("Lithuania", [event(2020, "Storm surge", "Kaunas", typ="Hydrological"),
                                              event(2021, "Flash floood", "Kaunas")])
        result = read_workbook(data, "Areas")
        used, left_out, issues = check_events(result.events, "Lithuania", areas=["Kaunas"], subtypes=result.subtypes)
        self.assertEqual(left_out, [])
        new = next(g for g in issues if g["key"] == "sub_new")
        self.assertEqual([r["row"] for r in new["rows"]], [2, 3])
        self.assertEqual(len(new["rows"]), 2)

    def test_subtype_added_to_lists_has_no_warning(self):
        data = generic_workbook("Lithuania", [event(2020, "Storm surge", "Kaunas", typ="Hydrological")])
        wb = load_workbook(io.BytesIO(data))
        lst = wb["Lists"]
        col = [c.value for c in lst[1]].index("Hazard sub-types") + 1
        last = max(r for r in range(1, lst.max_row + 1) if lst.cell(row=r, column=col).value)
        lst.cell(row=last + 1, column=col, value="Storm surge")
        out = io.BytesIO(); wb.save(out)
        result = read_workbook(out.getvalue(), "Areas")
        self.assertIn("Storm surge", result.subtypes)
        _, left_out, issues = check_events(result.events, "Lithuania", areas=["Kaunas"], subtypes=result.subtypes)
        self.assertEqual(left_out, [])
        self.assertNotIn("sub_new", {g["key"] for g in issues})

    def test_subtype_under_wrong_type_is_still_an_error(self):
        data = generic_workbook("Lithuania", [event(2020, "Earthquake", "Kaunas", typ="Hydrological")])
        result = read_workbook(data, "Areas")
        _, left_out, issues = check_events(result.events, "Lithuania", areas=["Kaunas"], subtypes=result.subtypes)
        self.assertEqual(len(left_out), 1)
        self.assertIn("sub", {g["key"] for g in issues})

    def test_area_column_with_another_name_is_found(self):
        """A workbook made with another set-up (for example "Wilayas") still reads in an app without that set-up."""
        data = generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas")])
        wb = load_workbook(io.BytesIO(data))
        ws = wb["3. Hazard list"]
        col = [c.value for c in ws[1]].index("Areas") + 1
        ws.cell(row=1, column=col, value="Wilayas")
        out = io.BytesIO(); wb.save(out)
        result = read_workbook(out.getvalue(), "Areas")
        self.assertIsNone(result.problem)
        self.assertEqual(result.events[0]["areas"], "Kaunas")




def add_to_lists(data, values):
    """Type values into empty cells at the bottom of columns in tab Lists. values: {header: [value, ...]}."""
    wb = load_workbook(io.BytesIO(data))
    lst = wb["Lists"]
    headers = [c.value for c in lst[1]]
    for header, vals in values.items():
        col = headers.index(header) + 1
        last = max([r for r in range(1, lst.max_row + 1) if lst.cell(row=r, column=col).value] or [1])
        for i, v in enumerate(vals, 1):
            lst.cell(row=last + i, column=col, value=v)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class WorkbookListsTests(unittest.TestCase):
    """Everything in tab Lists can be extended by the National Society without changing the app."""

    def check(self, data):
        result = read_workbook(data, "Areas")
        return result, check_events(result.events, "Lithuania", areas=["Kaunas"], workbook_lists=result.lists)

    def test_new_type_subtype_sector_and_factor_from_lists(self):
        row = event(2020, "Bark beetle outbreak", "Kaunas", typ="Forest health",
                    **{"Sectors affected": "Forestry", "Underlying factors (tags)": "Weak forest management"})
        data = add_to_lists(generic_workbook("Lithuania", [row]), {
            "Hazard types": ["Forest health"],
            "Hazard sub-types": ["Bark beetle outbreak"], "Sub-type belongs to": ["Forest health"],
            "Sectors": ["Forestry"],
            "Underlying factors": ["Weak forest management"], "Factor goes under": ["Political"]})
        result, (used, left_out, issues) = self.check(data)
        self.assertEqual(left_out, [])
        self.assertFalse({"type_new", "sub_new", "tags"} & {g["key"] for g in issues})
        self.assertEqual(result.lists["factors"]["Weak forest management"], "Political")

        from app.tree.rules import build_tree
        from app.workbook.checks import effective_lists
        tree = build_tree(used, {}, "Lithuania", "county", effective_lists(result.lists)["factors"])
        political = next(b for b in tree["context"] if b["id"] == "political")
        self.assertTrue(any("Weak forest management" in l["text"] for l in political["lines"]))
        self.assertTrue(any("Forest health" in l["text"] for b in tree["shock"] for l in b["lines"]))

    def test_unlisted_type_is_kept_with_a_warning(self):
        _, (used, left_out, issues) = self.check(generic_workbook("Lithuania", [
            event(2020, "Bark beetle outbreak", "Kaunas", typ="Forest health")]))
        self.assertEqual(len(used), 1)
        self.assertIn("type_new", {g["key"] for g in issues})

    def test_lists_can_move_a_subtype_to_another_type(self):
        """The workbook decides: if tab Lists puts Wildfire under Meteorological, that is what counts."""
        data = add_to_lists(generic_workbook("Lithuania", [event(2020, "Wildfire", "Kaunas", typ="Meteorological")]),
                            {"Hazard sub-types": [], })
        wb = load_workbook(io.BytesIO(data))
        lst = wb["Lists"]
        headers = [c.value for c in lst[1]]
        sub_col, type_col = headers.index("Hazard sub-types") + 1, headers.index("Sub-type belongs to") + 1
        row = next(r for r in range(2, lst.max_row + 1) if lst.cell(row=r, column=sub_col).value == "Wildfire")
        lst.cell(row=row, column=type_col, value="Meteorological")
        out = io.BytesIO(); wb.save(out)
        _, (used, left_out, issues) = self.check(out.getvalue())
        self.assertEqual(left_out, [])
        self.assertNotIn("sub", {g["key"] for g in issues})

    def test_old_workbook_without_new_columns_still_works(self):
        _, (used, left_out, _) = self.check(generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas")]))
        self.assertEqual((len(used), left_out), (1, []))


if __name__ == "__main__":
    unittest.main()
