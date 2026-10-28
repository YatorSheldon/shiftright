"""What the assistant knows about, and how to credit it.

The corpus is Australian workplace law as published on the Federal Register of
Legislation (www.legislation.gov.au), which licenses its content under Creative
Commons Attribution 4.0 International. The text is downloaded on the user's
machine at ingest time, split into sections and passages for search, and every
answer cites the section it relies on. This project is not affiliated with or
endorsed by the Office of Parliamentary Counsel or the Commonwealth.
"""

REGISTER_URL = "https://www.legislation.gov.au"
LICENCE_NAME = "Creative Commons Attribution 4.0 International"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"


def attribution(download_date: str) -> str:
    """The Register's required wording for content that has been changed (we split it into passages)."""
    return (
        f"Based on content from the Federal Register of Legislation at {download_date}. "
        "For the latest information on Australian Government legislation please go to https://www.legislation.gov.au."
    )


# Register IDs of the titles to index. "latest" always resolves to the current compilation.
TITLES = [
    {"id": "C2009A00028", "title": "Fair Work Act 2009", "cite": "s"},
    {"id": "F2009L02356", "title": "Fair Work Regulations 2009", "cite": "reg"},
]


def title_url(register_id: str) -> str:
    return f"{REGISTER_URL}/{register_id}/latest/text"
