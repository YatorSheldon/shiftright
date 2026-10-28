"""Split pages into short, self-describing passages for retrieval.

Each chunk keeps its page title and section heading, so a passage about
"Casual loading" still says which page and section it came from both when it
is searched and when it is shown to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shiftright.fetch import Page

TARGET_WORDS = 160
OVERLAP_WORDS = 30


@dataclass
class Chunk:
    id: str
    url: str
    page_title: str
    heading: str
    text: str

    @property
    def citation_url(self) -> str:
        return self.url

    @property
    def search_text(self) -> str:
        # Title and heading are repeated so they weigh in keyword search.
        return f"{self.page_title}. {self.heading}. {self.heading}. {self.text}"


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if s]


def chunk_page(page: Page, target_words: int = TARGET_WORDS, overlap_words: int = OVERLAP_WORDS) -> list[Chunk]:
    chunks: list[Chunk] = []
    slug = page.url.rstrip("/").rsplit("/", 1)[-1] or "page"
    for s_idx, section in enumerate(page.sections):
        sentences = _split_sentences(section.text)
        window: list[str] = []
        count = 0
        part = 0

        def emit(words: list[str], s_idx: int = s_idx, heading: str = section.heading) -> None:
            nonlocal part
            text = " ".join(words).strip()
            if text:
                chunks.append(Chunk(id=f"{slug}#{s_idx}.{part}", url=page.url, page_title=page.title, heading=heading, text=text))
                part += 1

        for sent in sentences:
            n = len(sent.split())
            if count + n > target_words and window:
                emit(window)
                # carry the tail of the previous window forward for context
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
