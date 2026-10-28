"""Download and clean the guidance pages (run on your own machine).

Polite by design: honours robots.txt, identifies itself, waits between
requests, and skips pages it already has unless you pass --refresh.
"""

from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from shiftright import __version__
from shiftright.sources import BASE_URL, URLS

USER_AGENT = f"ShiftRight/{__version__} (student portfolio project; non-commercial; +https://github.com/YatorSheldon/shiftright)"
DEFAULT_DELAY_S = 1.5
SKIP_HEADINGS = {"on this page:", "on this page", "related information", "tools and resources"}


@dataclass
class Section:
    heading: str
    text: str


@dataclass
class Page:
    url: str
    title: str
    sections: list[Section] = field(default_factory=list)
    source_reference: str = ""
    fetched_at: str = ""

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.url.removeprefix(BASE_URL).lower()).strip("-") or "home"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, url: str) -> Page:
    """Extract the title and heading-delimited sections from a guidance page."""
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("h1.page-title") or soup.find("title")
    title = _clean(title_el.get_text()) if title_el else url
    title = title.replace(" - Fair Work Ombudsman", "")

    body = soup.select_one("article.node .field--name-body") or soup.select_one("article.main") or soup.body
    ref_el = soup.select_one("p.sourceReference")
    source_reference = _clean(ref_el.get_text()).removeprefix("Source reference for page:").strip() if ref_el else ""

    sections: list[Section] = []
    heading, buf = title, []

    def flush():
        text = _clean(" ".join(buf))
        if text and heading.lower() not in SKIP_HEADINGS:
            sections.append(Section(heading=heading, text=text))

    if body is not None:
        # The "On this page:" jump list repeats headings; drop it and its links.
        for jump in body.select("h2.link-list"):
            nxt = jump.find_next_sibling()
            if nxt is not None and nxt.name in ("ul", "ol"):
                nxt.decompose()
            jump.decompose()
        for el in body.find_all(["h2", "h3", "h4", "p", "li", "td", "th"]):
            if el.find_parent(["nav", "aside", "footer"]):
                continue
            if el.name in ("h2", "h3", "h4"):
                flush()
                heading, buf = _clean(el.get_text()), []
            elif el.name == "li" and el.find_parent("li") is not None:
                continue  # nested list items are covered by their parent
            elif "sourceReference" not in (el.get("class") or []):
                text = el.get_text(" ")
                if text.strip():
                    buf.append(text)
        flush()

    return Page(url=url, title=title, sections=sections, source_reference=source_reference)


def _allowed(robots: urllib.robotparser.RobotFileParser, url: str) -> bool:
    try:
        return robots.can_fetch(USER_AGENT, url)
    except Exception:  # noqa: BLE001
        return True


def fetch_all(out_dir: Path, urls: list[str] = URLS, delay_s: float = DEFAULT_DELAY_S, refresh: bool = False) -> list[Path]:
    """Download every page in ``urls`` into ``out_dir`` as JSON. Returns the saved paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robots = urllib.robotparser.RobotFileParser(BASE_URL + "/robots.txt")
    try:
        robots.read()
    except Exception as exc:  # noqa: BLE001
        print(f"Couldn't read robots.txt ({exc}); continuing with the built-in page list.")

    saved: list[Path] = []
    for i, url in enumerate(urls, 1):
        slug = re.sub(r"[^a-z0-9]+", "-", url.removeprefix(BASE_URL).lower()).strip("-")
        path = out_dir / f"{slug}.json"
        if path.exists() and not refresh:
            saved.append(path)
            continue
        if not _allowed(robots, url):
            print(f"[{i}/{len(urls)}] skipped (robots.txt): {url}")
            continue
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"[{i}/{len(urls)}] failed: {url} ({exc})")
            continue
        page = parse_page(resp.text, url)
        page.fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path.write_text(json.dumps(asdict(page), ensure_ascii=False, indent=1))
        saved.append(path)
        print(f"[{i}/{len(urls)}] {page.title}: {len(page.sections)} sections")
        time.sleep(delay_s)
    return saved


def load_pages(raw_dir: Path) -> list[Page]:
    pages = []
    for path in sorted(raw_dir.glob("*.json")):
        d = json.loads(path.read_text())
        d["sections"] = [Section(**s) for s in d.get("sections", [])]
        pages.append(Page(**d))
    return pages
