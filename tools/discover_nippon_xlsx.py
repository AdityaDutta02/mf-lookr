#!/usr/bin/env python3
"""List every (period, xls_url) in Nippon India Mutual Fund's "Monthly Portfolio
Statement" archive — the SEBI-mandated full portfolio disclosure XLS, NOT the
marketing factsheet PDF (same PDF-vs-XLS distinction as PPFAS/HDFC, see
parse_nippon_xlsx.py's docstring).

Unlike PPFAS (a dedicated JSON-index page) or HDFC (a JSON API behind Akamai),
Nippon's single "Factsheet, Portfolio and Other Disclosures" page at
  https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures
lists every month's download link directly as plain server-rendered HTML — no bot
protection (confirmed: plain curl with a UA gets a 200 with the full archive back
to ~2012, verified against a Playwright-rendered snapshot of the same page — byte
counts of "MONTHLY-PORTFOLIO" occurrences matched between the two). No headless
browser or hidden AJAX/API call is needed for discovery.

Each row is an <li> with a "lhsLbl" label (the human description, e.g. "Monthly
portfolio for the month of June 2026") and an "rhsLbl" containing the actual
<a class="xls" href="...">Download</a> link. The page also lists "Debt Schemes
Portfolio" (fortnightly debt-only) and "Risk Parameter" disclosures in the same
list structure — filtered out here; only "Monthly portfolio ..." rows are the
full-fund detailed disclosure this project needs.

Filenames are NOT date-inferable in general (decades of naming drift — "NIMF-
MONTHLY-PORTFOLIO-30-Jun-26.xls", "Reliance-Monthly-Portfolios-31.10.2018.xls",
"Monthly-Portfolio-as-on-30-04-2021-with-Riskometer.xls", ...) so period comes
from the lhsLbl text (month name + 4-digit year), not the URL.
"""
import json
import re
import sys
from pathlib import Path

from http_util import fetch_text

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependency: pip install beautifulsoup4", file=sys.stderr)
    raise

PAGE_URL = "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    # Some months (confirmed: Aug-Sep 2020 through Feb 2021) use "the month end
    # <DD>th <Mon> <YYYY>" with an abbreviated month instead of the full name.
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Longest-alternative-first so "sept" matches before "sep" would truncate it, and
# full names match before their abbreviations (e.g. "June" before "jun").
MONTH_RE = re.compile("|".join(sorted(MONTHS.keys(), key=len, reverse=True)), re.IGNORECASE)
YEAR_RE = re.compile(r"(19|20)\d{2}")
ZW_RE = re.compile(r"[​‌‍﻿]")  # zero-width chars littered through the page's text nodes


def clean(text: str) -> str:
    return ZW_RE.sub("", text or "").strip()


def infer_period(label: str):
    m = MONTH_RE.search(label)
    y = YEAR_RE.search(label)
    if not m or not y:
        return None
    return f"{y.group(0)}-{MONTHS[m.group(0).lower()]:02d}"


def main():
    html = fetch_text(PAGE_URL)
    soup = BeautifulSoup(html, "html.parser")

    seen = {}
    skipped_other = 0
    for li in soup.find_all("li"):
        lhs = li.find("label", class_="lhsLbl")
        rhs = li.find("label", class_="rhsLbl")
        if not lhs or not rhs:
            continue
        label = clean(lhs.get_text())
        if not label.lower().startswith("monthly portfolio"):
            skipped_other += 1
            continue
        a = rhs.find("a", href=True)
        if not a:
            continue
        period = infer_period(label)
        if not period:
            print(f"  SKIP (no period parsed): {label!r}")
            continue
        url = "https://mf.nipponindiaim.com" + a["href"] if a["href"].startswith("/") else a["href"]
        # Keep the first (most-recently-listed, since the page lists newest-first)
        # URL per period — the page can list a revised/reuploaded file for the same
        # month further down; the top one is the current canonical link.
        seen.setdefault(period, url)

    entries = [{"period": p, "url": u} for p, u in sorted(seen.items())]
    out_path = Path(__file__).parent / "cache" / "nippon" / "xlsx_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, indent=2))
    if entries:
        print(f"Found {len(entries)} months: {entries[0]['period']} .. {entries[-1]['period']}")
    print(f"({skipped_other} non-monthly-portfolio rows skipped: debt/fortnightly/risk-parameter disclosures)")
    print(f"Manifest written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
