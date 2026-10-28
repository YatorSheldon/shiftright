"""Split legislation into short, self-describing passages for retrieval.

Most sections are short enough to be one passage. Long ones (definitions,
complex rules) are split at sentence boundaries with a small overlap. Every
passage keeps its title, section number, heading and Chapter/Part/Division
context, so "s 87 Entitlement to annual leave" still says where it came from
both when it is searched and when it is shown to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shiftright.fetch import Page

TARGET_WORDS = 200
OVERLAP_WORDS = 30


@dataclass
class Chunk:
    id: str
    url: str
    page_title: str  # e.g. "Fair Work Act 2009"
    heading: str  # e.g. "s 87 Entitlement to annual leave"
    text: str
    number: str = ""  # e.g. "87"
    context: str = ""  # e.g. "Part 2-2 > Division 6 Annual leave"

    @property
    def search_text(self) -> str:
        # The heading is repeated so it weighs more in keyword search.
        return f"{self.page_title}. {self.context}. {self.heading}. {self.heading}. {self.text}"

    @property
    def section_key(self) -> str:
        return f"{self.page_title}:{self.number}"


def _split_sentences(text: str) -> list[str]:
    # Split on sentence ends and on legislative list markers like " (2) " or " (a) ".
    parts = re.split(r"(?<=[.;:])\s+(?=\(?[A-Z0-9a-z])", text)
    return [p for p in parts if p.strip()]


def chunk_page(page: Page, target_words: int = TARGET_WORDS, overlap_words: int = OVERLAP_WORDS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in page.sections:
        heading = f"{page.cite} {section.label}".strip()
        sentences = _split_sentences(section.text)
        window: list[str] = []
        count = 0
        part = 0

        def emit(words: list[str], section=section, heading=heading) -> None:
            nonlocal part
            text = " ".join(words).strip()
            if text:
                chunks.append(
                    Chunk(
                        id=f"{page.title}:{section.number}#{part}",
                        url=section.url or page.url,
                        page_title=page.title,
                        heading=heading,
                        text=text,
                        number=section.number,
                        context=section.context,
                    )
                )
                part += 1

        for sent in sentences:
            n = len(sent.split())
            if count + n > target_words and window:
                emit(window)
                tail, tail_count = [], 0
                for prev in reversed(window):
                    tail_count += len(prev.split())
                    tail.insert(0, prev)
                    if tail_count >= overlap_words:
                        break
                window, count = tail, tail_count
            window.append(sent)
            count += n
        emit(window)
    return chunks


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    out: list[Chunk] = []
    for page in pages:
        out.extend(chunk_page(page))
    return out
