from shiftright.chunk import chunk_page
from shiftright.fetch import Page, Section, document_urls, parse_legislation

# Invented HTML that mirrors the Register's document structure: contents entries,
# Part/Division headings, ActHead5 section headings with CharSectno, body paragraphs.
DOC_URL = "https://www.legislation.gov.au/C0000A00000/2026-01-01/2026-01-01/text/original/epub/OEBPS/document_1/document_1.html"
HTML = """
<html><body>
<p class="TOC5"><span>5</span><span>Contents entry that must be skipped</span></p>
<p class="ActHead2"><a id="_Toc1"><span class="CharPartNo">Part&#xa0;2&#x2011;2</span><span>—</span><span>Standards</span></a></p>
<p class="ActHead3"><a id="_Toc2"><span class="CharDivNo">Division&#xa0;6</span><span>—</span><span>Annual leave</span></a></p>
<p id="navPoint_9" class="ActHead5"><a id="_Toc3"><span class="CharSectno">20</span><span>&#xa0; </span><span>Entitlement to annual leave</span></a></p>
<p class="subsection"><span>(1)</span><span>An employee is entitled to paid annual leave.</span></p>
<p class="paragraph"><span>(a)</span><span>accrued progressively;</span></p>
<p class="notetext">Note: this is invented test text.</p>
<p class="ActHead3"><a id="_Toc4"><span class="CharDivNo">Division&#xa0;7</span><span>—</span><span>Personal leave</span></a></p>
<p class="ActHead5"><a id="_Toc5"><span class="CharSectno">20A</span><span>&#xa0; </span><span>Entitlement to personal leave</span></a></p>
<p class="subsection"><span>An employee is entitled to personal leave.</span></p>
<p class="ActHead5"><a id="_Toc6"><span class="CharSectno">21</span><span>&#xa0; </span><span>Empty section is dropped</span></a></p>
<p class="ActHead1"><a id="_Toc7"><span>Schedule&#xa0;1</span><span>—</span><span>Transitional provisions</span></a></p>
<p class="ActHead5"><a id="_Toc8"><span class="CharSectno">20</span><span>&#xa0; </span><span>Transitional rule</span></a></p>
<p class="subsection"><span>An invented transitional clause.</span></p>
</body></html>
"""


def test_parse_legislation_sections_numbers_context_and_anchors():
    sections = parse_legislation(HTML, DOC_URL)
    assert [s.number for s in sections] == ["20", "20A", "Sch 1 cl 20"]  # schedule numbering kept distinct
    s20, s20a, _ = sections
    assert s20.heading == "Entitlement to annual leave"
    assert s20.context == "Part 2-2 — Standards > Division 6 — Annual leave"  # non-breaking hyphen normalised
    assert "entitled to paid annual leave" in s20.text and "accrued progressively" in s20.text
    assert "Contents entry" not in s20.text
    assert s20.url == DOC_URL + "#_Toc3"
    assert s20a.context.endswith("Division 7 — Personal leave")  # deeper context replaced, not appended


def test_document_urls_are_found_and_ordered():
    page = " ".join(
        f'<a href="https://www.legislation.gov.au/C0000A00000/v/text/original/epub/OEBPS/document_{n}/document_{n}.html#x">'
        for n in (10, 2, 1)
    )
    urls = document_urls(page, "C0000A00000")
    assert [u.rsplit("_", 1)[-1] for u in urls] == ["1.html", "2.html", "10.html"]


def test_chunks_carry_citation_and_respect_size():
    long_text = " ".join(f"({i}) An employee may take leave under rule {i}." for i in range(1, 80))
    page = Page(url="u", title="Example Act", cite="s", sections=[Section("87", "Leave", long_text, "Part 2", "u#87")])
    chunks = chunk_page(page, target_words=100, overlap_words=20)
    assert len(chunks) > 3
    assert all(c.heading == "s 87 Leave" and c.number == "87" and c.page_title == "Example Act" for c in chunks)
    assert all(len(c.text.split()) <= 100 + 20 + 15 for c in chunks)
    last = " ".join(chunks[0].text.split()[-6:])
    assert last in chunks[1].text  # overlap keeps context across chunk boundaries
    assert len({c.id for c in chunks}) == len(chunks)
    assert chunks[0].section_key == "Example Act:87"
