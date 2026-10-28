"""Which public guidance pages the assistant knows about, and how to credit them.

The pages are published by the Fair Work Ombudsman under the Creative Commons
Attribution-NonCommercial 4.0 International licence. This project downloads them
on the user's machine at ingest time instead of redistributing copies, credits
every answer to its source page, and is not affiliated with or endorsed by the
Fair Work Ombudsman or the Commonwealth.
"""

BASE_URL = "https://www.fairwork.gov.au"

ATTRIBUTION = "© Fair Work Ombudsman www.fairwork.gov.au"
LICENCE_NAME = "Creative Commons Attribution-NonCommercial 4.0 International"
LICENCE_URL = "https://creativecommons.org/licenses/by-nc/4.0/legalcode"
CHANGES_NOTE = "Page text was split into sections and short passages for search; wording is unchanged."

# Topics students and young workers ask about most: pay, casual work, leave,
# hours, starting and ending a job, unpaid work, and getting help.
PATHS = [
    "/pay-and-wages/minimum-wages",
    "/pay-and-wages/minimum-wages/junior-pay-rates",
    "/pay-and-wages/minimum-wages/pay-guides",
    "/pay-and-wages/minimum-wages/annualised-wages-and-salaries",
    "/pay-and-wages/minimum-wages/piece-rates-and-commission-payments",
    "/pay-and-wages/allowances-penalty-rates-and-other-penalties",
    "/pay-and-wages/paying-wages",
    "/pay-and-wages/pay-secrecy",
    "/pay-and-wages/deductions-and-related-issues",
    "/pay-and-wages/tax-and-superannuation",
    "/pay-and-wages/stand-downs",
    "/leave/annual-leave",
    "/leave/sick-and-carers-leave",
    "/leave/compassionate-and-bereavement-leave",
    "/leave/family-and-domestic-violence-leave",
    "/leave/parental-leave",
    "/leave/long-service-leave",
    "/leave/community-service-leave",
    "/leave/unpaid-leave",
    "/starting-employment/types-of-employees",
    "/starting-employment/types-of-employees/fixed-term-contract-employees",
    "/starting-employment/unpaid-work",
    "/starting-employment/probation",
    "/starting-employment/job-ads",
    "/starting-employment/before-starting-employment",
    "/employment-conditions/national-employment-standards",
    "/employment-conditions/awards",
    "/employment-conditions/agreements",
    "/employment-conditions/employment-contracts",
    "/employment-conditions/information-statements",
    "/employment-conditions/public-holidays",
    "/employment-conditions/hours-of-work-breaks-and-rosters",
    "/employment-conditions/right-to-disconnect",
    "/employment-conditions/flexibility-in-the-workplace",
    "/employment-conditions/protections-at-work",
    "/employment-conditions/bullying-in-the-workplace",
    "/employment-conditions/workplace-sexual-harassment",
    "/employment-conditions/workers-compensation",
    "/ending-employment/dismissal",
    "/ending-employment/resignation",
    "/ending-employment/redundancy",
    "/ending-employment/final-pay",
    "/ending-employment/help-with-termination",
    "/find-help-for/young-workers-and-students",
    "/find-help-for/young-workers-and-students/minimum-working-age",
    "/find-help-for/young-workers-and-students/get-ready-for-work",
    "/find-help-for/young-workers-and-students/pay-entitlements-and-working-conditions",
    "/find-help-for/young-workers-and-students/resolving-issues-and-getting-help",
    "/find-help-for/visa-holders-migrants",
    "/find-help-for/fast-food-restaurants-cafes",
    "/find-help-for/independent-contractors",
]

URLS = [BASE_URL + p for p in PATHS]
