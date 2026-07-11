#!/usr/bin/env python3
"""List every (period, xls_url) in PPFAS's "Detailed Portfolio Disclosure" archive.
Only available from 2019 onward (SEBI's monthly full-portfolio XLS mandate) — older
months only have the marketing factsheet PDF (see discover_ppfas.py / parse_ppfas.py)."""
import json
import re
import sys
from pathlib import Path

from http_util import fetch_text

INDEX_URL = "https://amc.ppfas.com/downloads/factsheet/index.php"
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
LINK_RE = re.compile(r'href="(/downloads/portfolio-disclosure/[^"]+?\.xls(?:\?[^"]*)?)"', re.IGNORECASE)
MONTH_RE = re.compile("|".join(MONTHS.keys()), re.IGNORECASE)
YEAR_RE = re.compile(r"(20[12]\d)")


def infer_period(path: str):
    m = MONTH_RE.search(path)
    if not m:
        return None
    path_only = path.split("?")[0]
    years = YEAR_RE.findall(path_only)
    if not years:
        return None
    return f"{years[-1]}-{MONTHS[m.group(0).lower()]:02d}"


def main():
    html = fetch_text(INDEX_URL)
    seen = {}
    for path in LINK_RE.findall(html):
        period = infer_period(path)
        if not period:
            continue
        url = "https://amc.ppfas.com" + path
        seen.setdefault(period, url)

    entries = [{"period": p, "url": u} for p, u in sorted(seen.items())]
    out_path = Path(__file__).parent / "cache" / "ppfas" / "xlsx_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, indent=2))
    if entries:
        print(f"Found {len(entries)} months: {entries[0]['period']} .. {entries[-1]['period']}")
    print(f"Manifest written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
