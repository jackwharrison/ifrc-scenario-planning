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
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Kyrgyzstan", "tree_type": "risk"})
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

    def test_post_without_token_is_refused(self):
        r = self.client.post("/start", data={"country": "Kyrgyzstan", "tree_type": "risk"})
        self.assertEqual(r.status_code, 400)

    def test_country_not_set_up(self):
        r = self.client.post("/start", data={"csrf": self.csrf, "country": "Lithuania", "tree_type": "risk"})
        self.assertEqual(r.status_code, 400)

    def test_template_download(self):
        r = self.client.get("/template/Kyrgyzstan.xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"PK"))

    def test_health(self):
        self.assertEqual(self.client.get("/health").get_json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
