#!/usr/bin/env python3
"""List every (period, xlsx_url) in Motilal Oswal MF's "Scheme Portfolio Details" /
"Month End Portfolio" archive — the SEBI-mandated monthly full portfolio disclosure
(ISIN + quantity per holding), NOT the marketing factsheet PDF under
/downloads/factsheets.

Motilal's site (Adobe AEM Edge Delivery) renders the downloads page entirely via
JS — there is no static link list to scrape. The actual data source is a backend
search API discovered by reading the page's block JS
(/blocks/our-funds-block/our-funds-block.js, dataMapMoObj.categoryfilter):

    GET /content/aem-cloud-dept-backend-motilal-oswal/api/search-documents.json
        ?year=&category=month end portfolio&month=&type=mf

Leaving year/month empty returns the FULL history in one call (316 docs as of
2026-07, June 2019 through July 2026) rather than paginating per month — much
cheaper than driving a browser through a year/month dropdown 80+ times.

That one category bucket also contains "Fortnightly Portfolio Report", "Half
Yearly Portfolio", and "Performance Direct/Regular Plan" documents mixed in
(same category tag on Motilal's CMS) — filtered out by requiring the title
contain "month end portfolio" (any spacing/hyphenation) or "scheme portfolio
details", which the genuine full monthly disclosures always do and the other
document types never do. A stray .pdf (interim "Multi Asset FoF" note) is
excluded by requiring an .xls/.xlsx path.

Period is inferred from the document TITLE text (month name + year), not the
filename or folder date — Motilal's own filenames are inconsistent (e.g. a doc
titled "...September 2025" has been seen filed under an "...october-2025.xlsx"
filename; the title is what a human maintainer actually meant to publish).
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

from http_util import fetch_text

ORIGIN = "https://www.motilaloswalmf.com"
API_PATH = "/content/aem-cloud-dept-backend-motilal-oswal/api/search-documents.json"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "sept": 9, "october": 10,
    "november": 11, "december": 12,
    "septempber": 9,  # genuine recurring typo in Motilal's own 2013/2014 titles
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_RE = re.compile(r"\b(" + "|".join(sorted(MONTHS.keys(), key=len, reverse=True)) + r")\b", re.I)
YEAR_RE = re.compile(r"(20[12]\d)")

# Genuine full-disclosure titles say "month end portfolio" (± hyphen/spacing) or
# "scheme portfolio details". Fortnightly/half-yearly/performance docs sharing the
# same CMS category never use either phrase.
RELEVANT_RE = re.compile(r"month[\s-]*end.*portfolio|scheme portfolio details", re.I)


def infer_period(title: str):
    m = MONTH_RE.search(title)
    y = YEAR_RE.search(title)
    if not m or not y:
        return None
    return f"{y.group(1)}-{MONTHS[m.group(1).lower()]:02d}"


def main():
    url = (
        f"{ORIGIN}{API_PATH}?year=&category="
        f"{urllib.parse.quote('month end portfolio')}&month=&type=mf"
    )
    raw = fetch_text(url)
    payload = json.loads(raw)
    results = payload.get("results", [])
    print(f"API returned {payload.get('totalMatches')} total docs in the category")

    seen = {}
    skipped_no_period = []
    for r in results:
        title = (r.get("title") or "").strip()
        path = r.get("path") or ""
        if not path.lower().endswith((".xls", ".xlsx")):
            continue
        if not RELEVANT_RE.search(title):
            continue
        period = infer_period(title)
        if not period:
            skipped_no_period.append(title)
            continue
        if period in seen:
            continue  # first-wins: API returns newest-uploaded-first, so the
            # first hit for a period is the most recently (re-)published version.
        seen[period] = {
            "period": period,
            "title": title,
            "url": ORIGIN + urllib.parse.quote(path),
        }

    entries = [seen[p] for p in sorted(seen.keys())]
    out_path = Path(__file__).parent / "cache" / "motilal" / "xlsx_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, indent=2))

    if entries:
        print(f"Found {len(entries)} months: {entries[0]['period']} .. {entries[-1]['period']}")
    if skipped_no_period:
        print(f"{len(skipped_no_period)} relevant-looking docs had no extractable period, skipped:")
        for t in skipped_no_period:
            print(f"  - {t!r}")
    print(f"Manifest written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
