import json
import tempfile
import unittest
from pathlib import Path

from vibedemo import images


def page(i, mime="image/jpeg", width=2000):
    return {"index": i, "title": "File:Photo %d.jpg" % i, "imageinfo": [{
        "mime": mime, "width": width, "thumburl": "https://upload.example/thumb%d.jpg" % i,
        "url": "https://upload.example/full%d.jpg" % i, "descriptionurl": "https://commons/p%d" % i,
        "extmetadata": {"Artist": {"value": '<a href="x">Jane &amp; Co</a>'},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}


def fake_fetch(pages):
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        if "api.php" in url:
            return json.dumps({"query": {"pages": pages}}).encode()
        return b"JPEGDATA"
    fetch.calls = calls
    return fetch


class ImagesTest(unittest.TestCase):
    def test_search_filters_and_cleans(self):
        pages = [page(3), page(1, mime="image/svg+xml"), page(2, width=300), page(4)]
        found = images.search("eiffel", 2, fetch=fake_fetch(pages))
        self.assertEqual([f["title"] for f in found], ["Photo 3.jpg", "Photo 4.jpg"])
        self.assertEqual(found[0]["author"], "Jane & Co")
        self.assertEqual(found[0]["url"], "https://upload.example/thumb3.jpg")

    def test_download_writes_files(self):
        fetch = fake_fetch([page(1), page(2), page(3)])
        with tempfile.TemporaryDirectory() as tmp:
            items = images.download("Paris skyline!", 2, tmp, fetch=fetch)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["paris-skyline-1.jpg", "paris-skyline-2.jpg"])
            self.assertEqual(Path(tmp, names[0]).read_bytes(), b"JPEGDATA")
            self.assertIn("CC BY-SA 4.0", images.credits_html(items))

    def test_nothing_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(images.ImageError):
                images.download("zzz", 2, tmp, fetch=fake_fetch([]))

    def test_network_error(self):
        def broken(url, timeout):
            raise images.ImageError("cannot reach Wikimedia Commons: timeout")
        with self.assertRaises(images.ImageError):
            images.search("x", 1, fetch=broken)


if __name__ == "__main__":
    unittest.main()
