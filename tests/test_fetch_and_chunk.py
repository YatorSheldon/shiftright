from shiftright.chunk import chunk_page
from shiftright.fetch import Page, Section, parse_page

# Invented HTML that mirrors the real page structure (title, body field, sections, source reference, nav noise).
HTML = """
<html><head><title>Example topic - Fair Work Ombudsman</title></head><body>
<nav><h2>Main navigation</h2><ul><li>Pay</li><li>Leave</li></ul></nav>
<article class="main">
  <h1 class="page-title">Example topic</h1>
  <article class="node node--type-basic-page">
    <div class="node__content"><div class="field field--name-body">
      <h2 class="link-list">On this page:</h2><ul><li><a href="#a">Part A</a></li></ul>
      <p>Intro paragraph about the example topic.</p>
      <h2>Part A</h2>
      <p>First fact about part A.</p>
      <ul><li>Point one <ul><li>nested detail</li></ul></li><li>Point two</li></ul>
      <h3>Detail</h3>
      <table><tr><th>Age</th><th>Rate</th></tr><tr><td>18</td><td>70%</td></tr></table>
      <p class="sourceReference">Source reference for page: Example Act sections 1-2</p>
    </div></div>
  </article>
</article>
</body></html>
"""


def test_parse_page_extracts_title_sections_and_reference():
    page = parse_page(HTML, "https://www.fairwork.gov.au/example")
    assert page.title == "Example topic"
    headings = [s.heading for s in page.sections]
    assert headings == ["Example topic", "Part A", "Detail"]  # "On this page:" is dropped
    assert "Intro paragraph" in page.sections[0].text
    part_a = page.sections[1].text
    assert "Point one" in part_a and "Point two" in part_a
    assert part_a.count("nested detail") == 1  # nested list text not duplicated
    assert "18" in page.sections[2].text and "70%" in page.sections[2].text
    assert page.source_reference == "Example Act sections 1-2"
    assert all("Main navigation" not in s.text for s in page.sections)


def test_chunks_carry_page_and_heading_and_respect_size():
    long_text = " ".join(f"Sentence number {i} about casual shifts and rosters." for i in range(80))
    page = Page(url="https://www.fairwork.gov.au/x/rosters", title="Rosters", sections=[Section("Changes", long_text)])
    chunks = chunk_page(page, target_words=100, overlap_words=20)
    assert len(chunks) > 3
    assert all(c.page_title == "Rosters" and c.heading == "Changes" for c in chunks)
    assert all(len(c.text.split()) <= 100 + 20 + 10 for c in chunks)
    # consecutive chunks overlap so context isn't cut mid-thought
    last_sentence = " ".join(chunks[0].text.split()[-8:])
    assert last_sentence in chunks[1].text
    assert len({c.id for c in chunks}) == len(chunks)
