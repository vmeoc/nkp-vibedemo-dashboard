"""Smoke tests for the web page (ticket T04). DO NOT MODIFY.

They only check the structure the JavaScript relies on.
The visual result is checked by a human in the browser.
"""
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "dashboard" / "static"


class UiFilesTest(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC / "index.html").read_text()
        self.js = (STATIC / "app.js").read_text()
        self.css = (STATIC / "style.css").read_text()

    def test_html_title(self):
        self.assertIn("NKP Vibecoding Demo", self.html)
        self.assertIn("Pipeline Monitor", self.html)

    def test_html_loads_assets(self):
        self.assertIn('/static/style.css', self.html)
        self.assertIn('/static/app.js', self.html)

    def test_html_required_ids(self):
        for element_id in ("banner", "mode", "sha", "last-refresh",
                           "group-developer", "group-nkp", "warning"):
            with self.subTest(id=element_id):
                self.assertIn(f'id="{element_id}"', self.html)

    def test_js_polls_api(self):
        self.assertIn("/api/status", self.js)
        self.assertIn("2000", self.js)
        self.assertIn("Dashboard server unreachable", self.js)

    def test_js_no_external_libraries(self):
        for word in ("import ", "require(", "http://", "https://"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.js)

    def test_css_has_status_classes(self):
        for status in ("pending", "running", "success", "failed"):
            with self.subTest(status=status):
                self.assertIn(f".status-{status}", self.css)


if __name__ == "__main__":
    unittest.main()
