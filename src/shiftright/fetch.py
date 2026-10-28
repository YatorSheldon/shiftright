"""Download legislation from the Federal Register of Legislation and split it into sections.

Polite by design: reads robots.txt and honours its Crawl-delay, identifies
itself, uses timeouts everywhere, stops after repeated failures, and reuses
files already on disk unless asked to refresh.

The Register serves each compilation as one or more clean HTML documents
(the same files behind its built-in reader). In those files every section
starts with a ``p.ActHead5`` heading whose number sits in ``span.CharSectno``,
and Chapter, Part and Division headings use ``ActHead2``..``ActHead4``.
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
from shiftright.sources import REGISTER_URL, TITLES, title_url

USER_AGENT = f"ShiftRight/{__version__} (student portfolio project; non-commercial; +https://github.com/YatorSheldon/shiftright)"
DEFAULT_DELAY_S = 10.0  # the Register's robots.txt Crawl-delay
MAX_CONSECUTIVE_FAILURES = 3

HEADING_CLASSES = {"ActHead1": 1, "ActHead2": 2, "ActHead3": 3, "ActHead4": 4}
SECTION_CLASS = "ActHead5"
SKIP_PREFIXES = ("TOC", "Header", "ShortT", "LongT", "CompiledActNo", "ENotes")
NUMBER_CLASSES = ("CharSectno",)


@dataclass
class Section:
    """One numbered provision, e.g. Fair Work Act 2009 s 87."""

    number: str
    heading: str
    text: str
    context: str = ""  # e.g. "Chapter 2 > Part 2-2 > Division 6 Annual leave"
    url: str = ""

    @property
    def label(self) -> str:
        return f"{self.number} {self.heading}".strip()


@dataclass
class Page:
    """One downloaded title (an Act or a set of Regulations)."""

    url: str
    title: str
    cite: str = "s"
    sections: list[Section] = field(default_factory=list)
    fetched_at: str = ""


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u2011", "-")  # non-breaking space and hyphen
    return re.sub(r"\s+", " ", text).strip()


def _classes(el) -> list[str]:
    return el.get("class") or []


def parse_legislation(html: str, doc_url: str) -> list[Section]:
    """Split one Register HTML document into numbered sections with their Chapter/Part/Division context."""
    soup = BeautifulSoup(html, "html.parser")
    context: dict[int, str] = {}
    sections: list[Section] = []
    current: Section | None = None
    buf: list[str] = []

    def flush():
        nonlocal current, buf
        if current is not None:
            current.text = _clean(" ".join(buf))
            if current.text:
                sections.append(current)
        current, buf = None, []

    for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5"]):
        cls = _classes(p)
        cls0 = cls[0] if cls else ""
        if cls0.startswith(SKIP_PREFIXES):
            continue
        if cls0 in HEADING_CLASSES:
            flush()
            level = HEADING_CLASSES[cls0]
            context[level] = _clean(p.get_text(" "))
            for deeper in [k for k in context if k > level]:
                del context[deeper]
            continue
        if cls0 == SECTION_CLASS:
            flush()
            num_el = p.find("span", class_=NUMBER_CLASSES)
            number = _clean(num_el.get_text()) if num_el else ""
            full = _clean(p.get_text(" "))
            heading = full[len(number) :].strip() if number and full.startswith(number) else full
            # The Register's own contents links point at the inner <a id="_Toc...">.
            inner = p.find("a", id=True)
            anchor = inner.get("id") if inner else p.get("id")
            # Schedules restart their numbering (Schedule 1 has its own clause 87),
            # so label them "Sch 1 cl 87" to keep them distinct from "s 87".
            schedule = next((re.match(r"Schedule\s+(\w+)", v) for v in context.values() if v.startswith("Schedule")), None)
            if schedule and number:
                number = f"Sch {schedule.group(1)} cl {number}"
            current = Section(
                number=number,
                heading=heading,
                text="",
                context=" > ".join(context[k] for k in sorted(context)),
                url=f"{doc_url}#{anchor}" if anchor else doc_url,
            )
            continue
        if current is not None:
            text = p.get_text(" ")
            if text.strip():
                buf.append(text)
    flush()
    return sections


class Fetcher:
    def __init__(self, delay_s: float | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.robots = urllib.robotparser.RobotFileParser()
        self.delay_s = DEFAULT_DELAY_S
        try:
            r = self.session.get(REGISTER_URL + "/robots.txt", timeout=15)
            r.raise_for_status()
            self.robots.parse(r.text.splitlines())
            crawl = self.robots.crawl_delay(USER_AGENT)
            if crawl:
                self.delay_s = float(crawl)
        except requests.RequestException as exc:
            print(f"Couldn't read robots.txt ({exc}); using a {self.delay_s:.0f}s delay.", flush=True)
            self.robots.parse([])
        if delay_s is not None:
            self.delay_s = max(delay_s, self.delay_s)
        self._last = 0.0
        self.failures = 0

    def get(self, url: str) -> str | None:
        if self.failures >= MAX_CONSECUTIVE_FAILURES:
            return None
        if not self.robots.can_fetch(USER_AGENT, url):
            print(f"Skipped (robots.txt): {url}", flush=True)
            return None
        wait = self._last + self.delay_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            self.failures += 1
            print(f"Failed: {url} ({exc})", flush=True)
            return None
        finally:
            self._last = time.monotonic()
        self.failures = 0
        return resp.content.decode("utf-8", errors="replace")


def document_urls(text_page_html: str, register_id: str) -> list[str]:
    """Find the compilation's HTML documents linked from a title's text page."""
    pattern = rf"https://www\.legislation\.gov\.au/{register_id}/[^\"'#\s]+/document_\d+\.html"
    urls = sorted(set(re.findall(pattern, text_page_html)), key=lambda u: int(re.search(r"document_(\d+)\.html", u).group(1)))
    return urls


def fetch_all(out_dir: Path, refresh: bool = False, delay_s: float | None = None) -> list[Path]:
    """Download every title in ``TITLES`` into ``out_dir`` as JSON. Returns the saved paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = None
    saved: list[Path] = []
    for t in TITLES:
        path = out_dir / f"{t['id']}.json"
        if path.exists() and not refresh:
            saved.append(path)
            continue
        fetcher = fetcher or Fetcher(delay_s)
        page_html = fetcher.get(title_url(t["id"]))
        if page_html is None:
            print(f"Couldn't download {t['title']}.", flush=True)
            continue
        docs = document_urls(page_html, t["id"])
        if not docs:
            print(f"No document links found for {t['title']}; the Register's page layout may have changed.", flush=True)
            continue
        sections: list[Section] = []
        for i, url in enumerate(docs, 1):
            html = fetcher.get(url)
            if html is None:
                break
            found = parse_legislation(html, url)
            sections.extend(found)
            print(f"{t['title']}: document {i}/{len(docs)}, {len(found)} sections", flush=True)
        else:
            page = Page(url=title_url(t["id"]), title=t["title"], cite=t["cite"], sections=sections)
            page.fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            path.write_text(json.dumps(asdict(page), ensure_ascii=False), encoding="utf-8")
            saved.append(path)
            continue
        print(f"Stopped part-way through {t['title']}; nothing saved for it.", flush=True)
    return saved


def load_pages(raw_dir: Path) -> list[Page]:
    pages = []
    for path in sorted(raw_dir.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        d["sections"] = [Section(**s) for s in d.get("sections", [])]
        pages.append(Page(**d))
    return pages
