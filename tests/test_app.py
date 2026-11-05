import io
import os
import re
import tempfile
import unittest

from app import create_app
from tests.helpers import example_bytes


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE_PATH": os.path.join(self.tmp.name, "test.db"),
                               "SESSION_COOKIE_SECURE": False})
        self.client = self.app.test_client()
        page = self.client.get("/start").get_data(as_text=True)
        self.csrf = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_flow(self):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Kyrgyzstan"})
        self.assertEqual(r.status_code, 302)
        tree_url = r.headers["Location"].rsplit("/", 1)[0]

        r = self.client.post(tree_url + "/upload", data={"csrf": self.csrf, "workbook": (io.BytesIO(example_bytes()), "kg.xlsx")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        self.assertIn("36 rows read", self.client.get(tree_url + "/check").get_data(as_text=True))

        r = self.client.post(tree_url + "/scores", data={"csrf": self.csrf, "l::Geohazards|Earthquake": "4",
                                                         "i::Geohazards|Earthquake": "5", "next": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("window.TREE", self.client.get(tree_url + "/tree").get_data(as_text=True))

        r = self.client.post(tree_url + "/edit", json={"action": "add", "box": "groups", "text": "Herders on summer pastures."},
                             headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(r.status_code, 200)
        groups = next(b for l in r.get_json()["view"]["layers"] for b in l["boxes"] if b["id"] == "groups")
        self.assertEqual(groups["mine"][0]["text"], "Herders on summer pastures.")

        page = self.client.get(tree_url + "/export").get_data(as_text=True)
        self.assertIn("Earthquake: risk 20 (High)", page)
        self.assertIn("Herders on summer pastures.", page)
        r = self.client.get(tree_url + "/export.docx")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"PK"))

        # Export options: Word or PDF, landscape or portrait
        from docx import Document
        r = self.client.get(tree_url + "/download?fmt=docx&orientation=portrait")
        section = Document(io.BytesIO(r.data)).sections[0]
        self.assertLess(section.page_width, section.page_height)
        self.assertIn("_portrait.docx", r.headers["Content-Disposition"])
        for orientation in ("landscape", "portrait"):
            r = self.client.get(tree_url + f"/download?fmt=pdf&orientation={orientation}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.mimetype, "application/pdf")
            self.assertTrue(r.data.startswith(b"%PDF"))
        self.assertEqual(self.client.get(tree_url + "/export.rtf").status_code, 404)

    def test_start_step_reachable_from_a_tree(self):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Lithuania", "area_label": "counties"})
        tree_url = r.headers["Location"].rsplit("/", 1)[0]
        page = self.client.get(tree_url + "/upload").get_data(as_text=True)
        self.assertIn(f'href="{tree_url}/start"', page)
        page = self.client.get(tree_url + "/start").get_data(as_text=True)
        self.assertIn('value="county"', page)
        r = self.client.post(tree_url + "/start", data={"csrf": self.csrf, "area_label": "Municipalities"})
        self.assertTrue(r.headers["Location"].endswith("/upload"))
        self.assertIn('value="municipality"', self.client.get(tree_url + "/start").get_data(as_text=True))

    def test_uploaded_workbook_can_be_downloaded(self):
        trees = []
        for country in ("Kyrgyzstan", "Lithuania"):
            r = self.client.post("/start", data={"csrf": self.csrf, "country": country})
            trees.append(r.headers["Location"].rsplit("/", 1)[0])
        data = example_bytes()
        for name in ("first.xlsx", "Hazard list with a very long name, final v2.xlsx"):
            self.client.post(trees[0] + "/upload", data={"csrf": self.csrf, "workbook": (io.BytesIO(data), name)},
                             content_type="multipart/form-data")
        page = self.client.get(trees[0] + "/check").get_data(as_text=True)
        links = re.findall(r'href="(/trees/\d+/uploads/(\d+))"', page)
        self.assertEqual(len({l for l, _ in links}), 2)  # newest plus one earlier upload
        self.assertIn("final v2.xlsx", page)
        newest = links[0][0]
        r = self.client.get(newest)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, data)
        self.assertIn("final v2.xlsx", r.headers["Content-Disposition"])
        # The home page links the latest workbook of each tree
        self.assertIn(newest, self.client.get("/").get_data(as_text=True))
        # An upload can only be fetched through its own tree
        other = trees[1] + "/uploads/" + links[0][1]
        self.assertEqual(self.client.get(other).status_code, 404)

    def test_post_without_token_is_refused(self):
        r = self.client.post("/start", data={"country": "Kyrgyzstan"})
        self.assertEqual(r.status_code, 400)

    def test_country_without_area_list_can_start(self):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Lithuania"})
        self.assertEqual(r.status_code, 302)

    def test_template_download(self):
        r = self.client.get("/template/Kyrgyzstan.xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"PK"))

    def test_footer_on_every_page(self):
        page = self.client.get("/start").get_data(as_text=True)
        self.assertIn("mailto:jack.harrison@ifrc.org", page)
        self.assertIn("https://github.com/jackwharrison/ifrc-scenario-planning", page)

    def test_health(self):
        self.assertEqual(self.client.get("/health").get_json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
