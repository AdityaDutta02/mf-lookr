#!/usr/bin/env python3
"""List every "Monthly Portfolio Disclosure" file in ICICI Prudential Mutual
Fund's "Other Scheme Disclosures" archive, via the JSON API the site itself
uses (apimf.icicipruamc.com — a real API, not HTML scraping; found by
inspecting the network tab on the Downloads page, same technique as HDFC's
discover_hdfc_xlsx.py). See http_util_icici.py's docstring for the two site
quirks (the "env: api" header requirement, and the broken archive.icicipruamc.com
redirect) this whole toolkit has to route around.

POST https://apimf.icicipruamc.com/nms/v1/downloads/files
  JSON body: {"categoryId": <subCategoryId>, "schemeCategory": "", "userType":
  "Investor", "fileType": "All", "page": <n>, "size": <n>, "filter": [],
  "categoryName": "OTHERS"}
  Paginated (no total count returned — just an "isNext" boolean per page).

categoryId here is the "Monthly Portfolio Disclosures" SUBcategory id under
the "Other Scheme Disclosures" top-level category
(confirmed via /nms/v1/downloads/categories?userType=Investor — that endpoint
lists ALL category/subcategory ids; hardcoded below since it's stable).

Unlike PPFAS (one workbook, many sheets) or HDFC (one file per scheme per
month), ICICI mostly bundles ALL schemes for a month into a single ZIP
("Monthly-Portfolio-Disclosure-<Month>-<Year>.zip", one .xlsx per scheme
inside) — but some months (mostly around scheme launches, or ad-hoc/interim
disclosures) also list loose standalone .xlsx/.xls/.pdf files alongside the
zip for that same period. Both kinds are recorded in the manifest; the
downloader unpacks zips and keeps loose files as-is; the parser only reads
.xlsx/.xls (loose .pdf entries — a handful of legacy 2019/2020-era files —
are skipped, same "PDF has no ISIN/quantity" reasoning as PPFAS's original
factsheet-PDF path).

Full history goes back to at least 2013 (354 entries covering 2013-2026 as of
this run) — much deeper than the SEBI 2019 floor PPFAS/HDFC hit, so no
hardcoded start-year floor is applied here.
"""
import json
import re
import sys
from pathlib import Path

from http_util_icici import post_json

CATEGORY_ID = "26a073d7-08d2-4a95-95fa-f83a4ee51e40"  # "Monthly Portfolio Disclosures" subcategory
API_URL = "https://apimf.icicipruamc.com/nms/v1/downloads/files"
ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "icici" / "xlsx_manifest.json"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_RE = re.compile(r"\b(" + "|".join(sorted(MONTHS.keys(), key=len, reverse=True)) + r")\b", re.IGNORECASE)
YEAR_RE = re.compile(r"(20[12]\d)")


def infer_period(title: str, file_date_ms):
    """Prefer the API's own fileDate (ms epoch) when present — reliable and
    locale-independent. Fall back to parsing the title text (older/looser
    entries sometimes have odd titles) only if fileDate is missing."""
    if file_date_ms:
        import datetime
        d = datetime.datetime.fromtimestamp(file_date_ms / 1000, tz=datetime.timezone.utc)
        return f"{d.year:04d}-{d.month:02d}"
    m = MONTH_RE.search(title)
    y = YEAR_RE.search(title)
    if not m or not y:
        return None
    return f"{y.group(1)}-{MONTHS[m.group(1).lower()]:02d}"


def fetch_page(page: int, size: int = 100):
    body = json.dumps({
        "categoryId": CATEGORY_ID, "schemeCategory": "", "userType": "Investor",
        "fileType": "All", "page": str(page), "size": str(size), "filter": [],
        "categoryName": "OTHERS",
    })
    raw = post_json(API_URL, body)
    payload = json.loads(raw)
    data = payload.get("success", {}).get("data", {})
    return data.get("files") or [], bool(data.get("isNext"))


def main():
    entries = []
    page = 1
    while True:
        files, is_next = fetch_page(page)
        if not files:
            break
        for f in files:
            title = (f.get("title") or {}).get("text") or ""
            url = f.get("url")
            if not url:
                continue
            period = infer_period(title, f.get("fileDate"))
            if not period:
                print(f"  SKIP (no period inferred): {title!r}")
                continue
            entries.append({"period": period, "title": title, "url": url})
        print(f"  page {page}: {len(files)} files, isNext={is_next}")
        if not is_next:
            break
        page += 1
        if page > 50:  # sanity bound — real archive is a few hundred entries across ~4 pages
            break

    entries.sort(key=lambda e: (e["period"], e["title"]))
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(entries, indent=2))
    periods = sorted(set(e["period"] for e in entries))
    print(f"\n{len(entries)} manifest entries across {len(periods)} months "
          f"({periods[0] if periods else '-'} .. {periods[-1] if periods else '-'})")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    sys.exit(main())
