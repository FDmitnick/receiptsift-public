import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILES = [
    ROOT / "content" / "resources.html",
    ROOT / "content" / "pdf-receipt-parser.html",
    ROOT / "content" / "receipt-to-csv.html",
    ROOT / "content" / "how-to-extract-data-from-pdf-receipts.html",
    ROOT / "content" / "receipt-parser-vs-manual-data-entry.html",
]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.h1_count = 0
        self.description = ""
        self.canonical = ""
        self.links: list[str] = []
        self.json_ld: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.h1_count += 1
        if tag == "title":
            self._capture = "title"
            self._buffer = []
        if tag == "script" and values.get("type") == "application/ld+json":
            self._capture = "json_ld"
            self._buffer = []
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "") or ""
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "") or ""
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "title":
            self.title = "".join(self._buffer).strip()
            self._capture = None
        if self._capture == "json_ld" and tag == "script":
            self.json_ld.append("".join(self._buffer).strip())
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def test_content_pages_have_unique_search_metadata_and_valid_schema():
    titles: set[str] = set()
    descriptions: set[str] = set()
    for path in CONTENT_FILES:
        page = parse_page(path)
        assert page.title and page.title not in titles
        assert page.description and page.description not in descriptions
        assert page.h1_count == 1
        assert page.canonical.startswith("{{BASE_URL}}/")
        assert page.json_ld
        for payload in page.json_ld:
            json.loads(payload.replace("{{BASE_URL}}", "https://example.com"))
        titles.add(page.title)
        descriptions.add(page.description)


def test_content_pages_are_connected_by_crawlable_internal_links():
    expected_paths = {
        "/resources",
        "/pdf-receipt-parser",
        "/receipt-to-csv",
        "/guides/how-to-extract-data-from-pdf-receipts",
        "/compare/receipt-parser-vs-manual-data-entry",
    }
    all_links: list[str] = []
    for path in CONTENT_FILES:
        all_links.extend(parse_page(path).links)
    assert expected_paths.issubset(set(all_links))
    assert all(re.match(r"^(?:/|#|mailto:|https://)", link) for link in all_links)
