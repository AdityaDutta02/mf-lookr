#!/usr/bin/env python3
"""List every (period, scheme_name, xlsx_url) in Invesco Mutual Fund's
"Monthly Portfolio Statement" archive — the SEBI-mandated detailed
disclosure (ISIN + quantity per holding), NOT the marketing factsheet PDF
under the site's "Factsheets" tab (see the task brief / parse_ppfas_xlsx.py's
docstring for why that distinction matters).

The real source is a JSON API the site's own "Complete Monthly Holdings" tab
(literature-and-form?tab=Complete) calls — found by reading that page's
inline <script> (no headless browser needed here, unlike HDFC's Akamai-
fronted case; a plain curl with a UA + Referer works):

  GET https://invescomutualfund.com/api/ClassificationCompleteMonthlyHoldings?page=Holding
    -> [{"FunClassificationValue": "equity", ...}, ...]  (the fund-type tabs)
  GET https://invescomutualfund.com/api/CompleteMonthlyHoldings
    -> [{"Year": 2026}, {"Year": 2025}, ...]              (years the year-picker offers)
  GET https://invescomutualfund.com/api/CompleteMonthlyHoldings?year=<Y>&classification=<c>
    -> [{"Name": "<scheme>", "JanUrl": "...", "JanName": "01/26", ... (Jan..Dec)}, ...]
       one row per scheme in that classification, one URL per month (empty
       string "" for months not yet published/not applicable).

Confirmed by direct inspection: files are real OOXML regardless of the
served extension (.xlsx recent, .xls pre-~2020) — same "extension lies"
quirk PPFAS's and HDFC's archives have (see parse_invesco_xlsx.py).
"""
import json
import sys
import time
from pathlib import Path

from http_util_invesco import fetch_json

API_BASE = "https://invescomutualfund.com/api/CompleteMonthlyHoldings"
CLASSIFICATION_API = "https://invescomutualfund.com/api/ClassificationCompleteMonthlyHoldings?page=Holding"

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "invesco" / "xlsx_manifest.json"

MONTH_KEYS = [
    ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4), ("May", 5), ("Jun", 6),
    ("Jul", 7), ("Aug", 8), ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
]


def get_classifications():
    raw = fetch_json(CLASSIFICATION_API)
    data = json.loads(raw)
    return [c["FunClassificationValue"] for c in data]


def get_years():
    raw = fetch_json(API_BASE)
    data = json.loads(raw)
    return sorted((y["Year"] for y in data), reverse=True)


def fetch_year_classification(year: int, classification: str):
    """Returns list of {scheme_name, period, url}, [] on failure/empty (never raises —
    one bad (year, classification) combo shouldn't kill the whole discovery run)."""
    try:
        raw = fetch_json(f"{API_BASE}?year={year}&classification={classification}")
        data = json.loads(raw)
    except Exception as ex:
        print(f"  {year} {classification}: FAILED — {ex}")
        return []
    out = []
    for row in data:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        for key, month in MONTH_KEYS:
            url = row.get(f"{key}Url")
            if not url:
                continue
            out.append({"period": f"{year}-{month:02d}", "scheme_name": name, "url": url})
    return out


def main():
    classifications = get_classifications()
    years = get_years()
    print(f"Classifications: {classifications}")
    print(f"Years offered by site: {years[0]}..{years[-1]} ({len(years)} years)")

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    seen = {(e["period"], e["scheme_name"]) for e in manifest}

    for year in years:
        new_this_year = 0
        for c in classifications:
            entries = fetch_year_classification(year, c)
            for e in entries:
                key = (e["period"], e["scheme_name"])
                if key in seen:
                    continue
                seen.add(key)
                manifest.append(e)
                new_this_year += 1
            time.sleep(0.15)
        print(f"  {year}: {new_this_year} new entries")
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    periods = sorted(set(e["period"] for e in manifest))
    print(f"\n{len(manifest)} manifest entries across {len(periods)} months "
          f"({periods[0] if periods else '-'} .. {periods[-1] if periods else '-'})")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    sys.exit(main())
