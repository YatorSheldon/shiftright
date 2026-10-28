"""Shared fixtures. The provisions below are invented test text, not real legislation."""

import pytest

from shiftright.chunk import chunk_pages
from shiftright.fetch import Page, Section
from shiftright.index import Index

DOC = "https://www.legislation.gov.au/TEST/doc.html"


@pytest.fixture()
def pages():
    return [
        Page(
            url="https://www.legislation.gov.au/TEST/latest/text",
            title="Example Workplace Act",
            cite="s",
            sections=[
                Section(
                    "10",
                    "Meaning of casual employee",
                    "A casual employee is a person offered work with no firm advance commitment to continuing and indefinite work.",
                    "Part 1 > Division 2 Definitions",
                    DOC + "#s10",
                ),
                Section(
                    "20",
                    "Entitlement to annual leave",
                    "(1) For each year of service, an employee other than a casual employee is entitled to paid annual leave. "
                    "(2) Annual leave accrues progressively according to ordinary hours of work.",
                    "Part 2 > Division 6 Annual leave",
                    DOC + "#s20",
                ),
                Section(
                    "21",
                    "Payment for annual leave on termination",
                    "If employment ends and an employee has untaken paid annual leave, the employer must pay the employee for that leave.",
                    "Part 2 > Division 6 Annual leave",
                    DOC + "#s21",
                ),
                Section(
                    "30",
                    "Employer obligations in relation to pay slips",
                    "An employer must give each employee a pay slip within one working day of paying the employee.",
                    "Part 5 > Division 3 Records and pay slips",
                    DOC + "#s30",
                ),
            ],
        )
    ]


@pytest.fixture()
def index(pages):
    return Index(chunk_pages(pages))
