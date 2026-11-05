"""Tab 4 (seasonal calendar) and tab 5 (sources): read from the workbook, shown on the Calendar view."""
import io
import os
import re
import tempfile
import unittest

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from app import create_app
from app.workbook.checks import check_seasonal
from app.workbook.reader import read_workbook
from tests.helpers import event, example_bytes, generic_workbook


def with_calendar(data, rows, sources):
    """rows: [(label, category, months or fill-months, sources text)]; months given as 'x' marks or ('fill', [..])."""
    wb = load_workbook(io.BytesIO(data))
    cal, src = wb["4. Seasonal calendar"], wb["5. Sources"]
    for i, (label, cat, months, refs) in enumerate(rows, 2):
        cal.cell(row=i, column=1, value=label)
        cal.cell(row=i, column=2, value=cat)
        if months and months[0] == "fill":
            for m in months[1]:
                cal.cell(row=i, column=3 + m).fill = PatternFill("solid", fgColor="9BC2E6")
        else:
            for m in months:
                cal.cell(row=i, column=3 + m, value="x")
        cal.cell(row=i, column=15, value=refs)
    for i, (group, title, link) in enumerate(sources, 2):
        src.cell(row=i, column=2, value=group)
        src.cell(row=i, column=3, value=title)
        src.cell(row=i, column=4, value=link)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class SeasonalReadTests(unittest.TestCase):
    def test_marks_fills_and_sources(self):
        data = with_calendar(generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas")]),
                             [("Winter", "Meteorological", [11, 0, 1], "1; 2"),
                              ("Planting", "Agricultural", ("fill", [3, 4]), "2"),
                              ("Elections", "Societal", [], "7")],
                             [("Seasons", "Source A", "https://a.example/x"),
                              ("Farming", "Source B", "https://b.example/1 https://b.example/2")])
        s = read_workbook(data, "Areas").seasonal
        self.assertEqual([r["months"] for r in s["rows"]], [[0, 1, 11], [3, 4], []])
        self.assertEqual(s["rows"][0]["sources"], [1, 2])
        self.assertEqual(s["sources"][1]["links"], ["https://b.example/1", "https://b.example/2"])
        keys = {g["key"] for g in check_seasonal(s)}
        self.assertEqual(keys, {"cal_months", "cal_sources"})

    def test_workbook_without_tabs_4_and_5(self):
        s = read_workbook(generic_workbook("Lithuania", [event(2020, "Flash flood", "Kaunas")]), "Areas").seasonal
        self.assertEqual(s, {"rows": [], "sources": []})

    def test_kyrgyzstan_example_has_a_calendar(self):
        s = read_workbook(example_bytes(), "Oblasts").seasonal
        self.assertEqual(len(s["rows"]), 20)
        self.assertEqual(len(s["sources"]), 16)
        winter = s["rows"][0]
        self.assertEqual((winter["label"], winter["months"]), ("Cold / winter season", [0, 1, 2, 10, 11]))


class SeasonalPageTests(unittest.TestCase):
    def test_calendar_in_tree_payload(self):
        tmp = tempfile.TemporaryDirectory()
        app = create_app({"TESTING": True, "DATABASE_PATH": os.path.join(tmp.name, "t.db"), "SESSION_COOKIE_SECURE": False})
        c = app.test_client()
        csrf = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/start").get_data(as_text=True)).group(1)
        url = c.post("/start", data={"csrf": csrf, "country": "Kyrgyzstan"}).headers["Location"].rsplit("/", 1)[0]
        c.post(url + "/use-example", data={"csrf": csrf})
        check = c.get(url + "/check").get_data(as_text=True)
        self.assertIn("Tab 4, row", check)              # the one seasonal row without a source
        self.assertIn("<b>16</b><span>rows with warnings</span>", check)   # tab 4 rows are not counted with tab 3
        page = c.get(url + "/tree").get_data(as_text=True)
        self.assertIn('"seasonal": {"rows": [{', page)
        self.assertIn("Cold / winter season", page)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
