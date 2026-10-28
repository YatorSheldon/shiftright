"""Shared fixtures. The pages below are invented test text, not real guidance."""

import pytest

from shiftright.chunk import chunk_pages
from shiftright.fetch import Page, Section
from shiftright.index import Index

BASE = "https://www.fairwork.gov.au"


@pytest.fixture()
def pages():
    return [
        Page(
            url=BASE + "/test/casual-work",
            title="Casual work",
            sections=[
                Section(
                    "What casual means",
                    "A casual employee has no firm advance commitment to ongoing work. Casual employees can be offered shifts as needed.",
                ),
                Section(
                    "Casual loading",
                    "Casual employees receive a casual loading on top of the base hourly rate. The loading compensates for not getting paid leave.",
                ),
            ],
        ),
        Page(
            url=BASE + "/test/unpaid-trials",
            title="Unpaid trials",
            sections=[
                Section(
                    "Trial shifts",
                    "An unpaid trial shift is only allowed when it is needed to demonstrate the skills for the job. It must be supervised and kept short.",
                ),
                Section(
                    "Internships",
                    "Placements that are a required part of a university course can be unpaid. Other unpaid internships may be unlawful if the person is really an employee.",
                ),
            ],
        ),
        Page(
            url=BASE + "/test/annual-leave",
            title="Annual leave",
            sections=[
                Section(
                    "How much leave",
                    "Full-time employees accumulate annual leave throughout the year based on the hours they work. Part-time employees accumulate leave on a pro rata basis.",
                ),
                Section(
                    "Leaving a job",
                    "Unused annual leave is paid out in the final pay when employment ends. It is paid at the rate the employee would have received.",
                ),
            ],
        ),
    ]


@pytest.fixture()
def index(pages):
    return Index(chunk_pages(pages))
