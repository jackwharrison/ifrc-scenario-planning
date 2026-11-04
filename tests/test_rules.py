import unittest

from app.tree.rules import apply_edits, build_tree, kept_lines
from app.workbook.checks import check_events
from app.workbook.reader import read_workbook
from tests.helpers import example_bytes


def events():
    used, _, _ = check_events(read_workbook(example_bytes(), "Oblasts").events, "Kyrgyzstan")
    return used


def find(tree, layer, box, line_id):
    b = next(b for b in tree[layer] if b["id"] == box)
    return next(l for l in b["lines"] if l["id"] == line_id)


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.tree = build_tree(events(), {}, "Kyrgyzstan")

    def test_deaths(self):
        line = find(self.tree, "impact", "people", "k")
        self.assertEqual(line["text"], "At least 776 people killed in 15 events with a recorded death toll.")
        self.assertEqual(len(line["rows"]), 15)

    def test_houses_and_share(self):
        self.assertEqual(find(self.tree, "impact", "systems", "h")["text"],
                         "At least 22,543 houses damaged or destroyed across 9 events.")
        self.assertEqual(find(self.tree, "impact", "systems", "ht")["text"],
                         "Earthquake events account for 16,802 of them (75%).")

    def test_seasonality(self):
        self.assertEqual(find(self.tree, "shock", "season", "s-wet")["text"],
                         "7 of 9 floods, mudflows and landslides started between March and June.")

    def test_areas_skip_national(self):
        texts = [l["text"] for l in next(b for b in self.tree["priorities"] if b["id"] == "areas")["lines"]]
        self.assertTrue(texts[0].startswith("Osh: 13 events"))
        self.assertFalse(any(t.startswith("National") for t in texts))

    def test_acronyms_keep_capitals(self):
        tree = build_tree(events(), {"Biological|COVID-19": {"l": 4, "i": 4}}, "Kyrgyzstan")
        self.assertIn("COVID-19", tree["shock_title"])

    def test_no_priorities_without_scores(self):
        box = next(b for b in self.tree["shock"] if b["id"] == "hazards")
        self.assertEqual(box["lines"], [])
        self.assertTrue(box["needs_scores"])

    def test_scores_make_priorities(self):
        tree = build_tree(events(), {"Geohazards|Earthquake": {"l": 4, "i": 5}, "Societal|Civil unrest": {"l": 3, "i": 3}},
                          "Kyrgyzstan")
        lines = next(b for b in tree["shock"] if b["id"] == "hazards")["lines"]
        self.assertEqual([l["text"] for l in lines], ["Earthquake: risk 20 (High), likelihood 4, impact 5."])

    def test_edits_and_left_out(self):
        view = apply_edits(self.tree, {"k": "Edited wording."}, {"kt": True}, {"people": [{"id": "u1", "text": "Mine."}]})
        people = next(b for l in view["layers"] for b in l["boxes"] if b["id"] == "people")
        self.assertEqual(kept_lines(people)[0], "Edited wording.")
        self.assertNotIn(find(self.tree, "impact", "people", "kt")["text"], kept_lines(people))
        self.assertEqual(kept_lines(people)[-1], "Mine.")

    def test_few_events_no_pattern(self):
        few = [e for e in events() if e["sub"] == "Landslide"][:2]
        tree = build_tree(few, {}, "Kyrgyzstan")
        line = next(b for b in tree["shock"] if b["id"] == "season")["lines"][0]
        self.assertIn("too few to show a seasonal pattern", line["text"])


if __name__ == "__main__":
    unittest.main()
