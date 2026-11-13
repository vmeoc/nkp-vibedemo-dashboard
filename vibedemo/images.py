"""Free images for the vibecoded page, from Wikimedia Commons.

One search request, parallel downloads of resized thumbnails (fast: a few
seconds), files saved in app/images/ so they are baked into the container image
(the deployed page needs no Internet access). Credits are returned so the page
can show attribution, as required by most Commons licences.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "vibedemo/1.0 (NKP vibecoding demo; https://github.com/vmeoc/nkp-vibedemo-dashboard)"
ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp")
TAG = re.compile(r"<[^>]+>")


class ImageError(Exception):
    pass


def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # network errors of all kinds
        raise ImageError("cannot reach Wikimedia Commons: %s" % exc)


def slugify(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "image"


def _clean(value: str) -> str:
    return html.unescape(TAG.sub("", value or "")).strip()


def search(query: str, count: int, width: int = 1280, timeout: float = 8.0, fetch=_get) -> list:
    """Return up to `count` candidates: dicts with url, title, author, licence, page."""
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrnamespace": "6",
        "gsrsearch": "%s filetype:bitmap" % query,
        "gsrlimit": str(max(count * 4, 10)),
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": str(width),
        "iiextmetadatafilter": "Artist|LicenseShortName",
    }
    raw = fetch(API + "?" + urllib.parse.urlencode(params), timeout)
    try:
        pages = json.loads(raw).get("query", {}).get("pages", [])
    except ValueError:
        raise ImageError("unexpected answer from Wikimedia Commons")
    pages = sorted(pages, key=lambda p: p.get("index", 0))
    results = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ALLOWED_MIME:
            continue
        if (info.get("width") or 0) < 800:          # skip icons and tiny pictures
            continue
        meta = info.get("extmetadata") or {}
        results.append({
            "url": info.get("thumburl") or info.get("url"),
            "title": page.get("title", "").replace("File:", ""),
            "author": _clean((meta.get("Artist") or {}).get("value", "")) or "Unknown author",
            "licence": _clean((meta.get("LicenseShortName") or {}).get("value", "")) or "see source",
            "page": info.get("descriptionurl", ""),
        })
        if len(results) >= count:
            break
    return results


def download(query: str, count: int, out_dir, timeout: float = 15.0, fetch=_get) -> list:
    """Search and download. Returns the candidates with a 'file' key added."""
    count = max(1, min(count, 8))
    found = search(query, count, fetch=fetch)
    if not found:
        raise ImageError("no image found for %r - try a simpler or English query" % query)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = slugify(query)

    def grab(item_index):
        index, item = item_index
        ext = ".png" if item["url"].lower().endswith(".png") else ".jpg"
        path = out / ("%s-%d%s" % (base, index, ext))
        path.write_bytes(fetch(item["url"], timeout))
        item["file"] = path
        return item

    with ThreadPoolExecutor(max_workers=len(found)) as pool:
        return list(pool.map(grab, enumerate(found, start=1)))


def credits_html(items: list) -> str:
    parts = ['<a href="%s">%s</a> by %s (%s)' % (
        html.escape(i["page"]), html.escape(i["title"]), html.escape(i["author"]),
        html.escape(i["licence"])) for i in items]
    return "Images: " + " · ".join(parts) + " - via Wikimedia Commons"
