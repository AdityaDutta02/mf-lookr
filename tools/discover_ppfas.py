#!/usr/bin/env python3
"""List every (period, pdf_url) in PPFAS's factsheet archive.

The page's URL pattern is NOT stable across years — 2019+ mostly follows
/downloads/factsheet/{YYYY}/ppfas-mf-factsheet-for-{Month}-{YYYY}.pdf, but
2014-2018 vary (pltvf-factsheet-*, PPFCF-factsheet-*, some with /month/ path
segments, some without). So: catch every .pdf href under
/downloads/factsheet/ (excluding /digital-factsheet/, a separate marketing
HTML archive we don't want), then infer (year, month) from whichever year+
month tokens appear in the URL.
"""
import json
import re
import sys
from pathlib import Path

from http_util import fetch_text

BASE = "https://amc.ppfas.com/downloads/factsheet/"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_ALT = "|".join(MONTHS.keys())

PDF_HREF_RE = re.compile(r'href="(/downloads/factsheet/[^"]+?\.pdf(?:\?[^"]*)?)"', re.IGNORECASE)
YEAR_RE = re.compile(r"(20[12]\d)")
MONTH_RE = re.compile(MONTH_ALT, re.IGNORECASE)


def infer_period(path: str):
    m = MONTH_RE.search(path)
    y = YEAR_RE.findall(path)
    if not m or not y:
        return None
    month_num = MONTHS[m.group(0).lower()]
    # A URL can contain two years (dir year + cache-bust query year); the correct
    # one is whichever appears BEFORE the .pdf (i.e. in the path/filename, not the query string).
    path_only = path.split("?")[0]
    y_path = YEAR_RE.findall(path_only)
    year = y_path[-1] if y_path else y[0]
    return f"{year}-{month_num:02d}"


def main():
    html = fetch_text(BASE)
    seen = {}
    skipped = []
    for path in PDF_HREF_RE.findall(html):
        if "/digital-factsheet/" in path.lower():
            continue
        period = infer_period(path)
        url = "https://amc.ppfas.com" + path if path.startswith("/") else path
        if not period:
            skipped.append(path)
            continue
        # Page lists newest cache-busted link first per period; keep first seen.
        seen.setdefault(period, url)

    entries = [{"period": p, "url": u} for p, u in sorted(seen.items())]
    out_path = Path(__file__).parent / "cache" / "ppfas" / "manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, indent=2))
    print(f"Found {len(entries)} months: {entries[0]['period']} .. {entries[-1]['period']}")
    print(f"Manifest written to {out_path}")
    if skipped:
        print(f"Skipped {len(skipped)} .pdf hrefs (no inferrable period), e.g.: {skipped[:5]}")


if __name__ == "__main__":
    sys.exit(main())
