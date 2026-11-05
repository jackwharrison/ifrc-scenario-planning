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


if __name__ == "__main__":
    unittest.main()
