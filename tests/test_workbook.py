import io
import unittest

from app import create_app
from app.workbook.checks import check_events
from app.workbook.reader import read_workbook
from app.workbook.template import build_template
from tests.helpers import example_bytes, modified_example


class ReaderTests(unittest.TestCase):
    def test_reads_example(self):
        result = read_workbook(example_bytes(), "Oblasts")
        self.assertIsNone(result.problem)
        self.assertEqual(len(result.events), 36)
        first = result.events[0]
        self.assertEqual(first["_row"], 2)
        self.assertEqual(first["year"], 2002)
        self.assertEqual(first["sub"], "Mining accident")

    def test_area_column_found_by_position(self):
        """The area column may have another name (Oblasts, Wilayas...): it sits right after Hazard sub-type."""
        result = read_workbook(example_bytes(), "Regions")
        self.assertIsNone(result.problem)
        self.assertEqual(len(result.events), 36)

    def test_missing_column_is_old_layout(self):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(example_bytes()))
        ws = wb["3. Hazard list"]
        col = [c.value for c in ws[1]].index("Verified") + 1
        ws.cell(row=1, column=col, value="Checked")
        out = io.BytesIO(); wb.save(out)
        result = read_workbook(out.getvalue(), "Oblasts")
        self.assertEqual(result.problem["kind"], "old_layout")
        self.assertIn("Verified", result.problem["missing"])

    def test_not_excel(self):
        self.assertEqual(read_workbook(b"not a workbook", "Oblasts").problem["kind"], "broken")

    def test_template_round_trip(self):
        """The generated blank template must be readable by the reader (no rows, no problems)."""
        with create_app({"TESTING": True, "DATABASE_PATH": ":memory:"}).app_context():
            data = build_template("Kyrgyzstan")
        result = read_workbook(data, "Oblasts")
        self.assertIsNone(result.problem)
        self.assertEqual(result.events, [])


class CheckTests(unittest.TestCase):
    def check(self, data):
        return check_events(read_workbook(data, "Oblasts").events, "Kyrgyzstan")

    def test_example_has_warnings_but_no_errors(self):
        used, left_out, issues = self.check(example_bytes())
        self.assertEqual(len(used), 36)
        self.assertEqual(left_out, [])
        keys = {g["key"] for g in issues}
        self.assertIn("area", keys)        # two events have no oblast
        self.assertIn("verified", keys)    # two events are not verified
        self.assertTrue(all(g["level"] == "warning" for g in issues))

    def test_errors_leave_rows_out(self):
        data = modified_example({(2, "Hazard sub-type"): "Earthquake",   # belongs to Geohazards, not Technological
                                 (3, "Start month"): "Spring",
                                 (4, "Oblasts"): "Atlantis"})
        used, left_out, issues = self.check(data)
        self.assertEqual(len(used), 33)
        self.assertEqual(sorted(e["_row"] for e in left_out), [2, 3, 4])
        errors = {g["key"] for g in issues if g["level"] == "error"}
        self.assertEqual(errors, {"sub", "start", "area_bad"})

    def test_deaths_in_notes_but_not_in_column(self):
        _, _, issues = self.check(example_bytes())
        killed = next(g for g in issues if g["key"] == "killed")
        self.assertTrue(any(r["year"] == 2020 for r in killed["rows"]))   # COVID-19 row


if __name__ == "__main__":
    unittest.main()
