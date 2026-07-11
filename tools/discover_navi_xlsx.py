#!/usr/bin/env python3
"""List every (period, scheme_name, xlsx_url) in Navi Mutual Fund's "Monthly
Portfolio Statement" archive, via the WP REST route the site's own dropdown
JS calls (POST nv/v1/documents, category=884/type=Monthly — see
http_util_navi.py's docstring for how the nonce works and why no cookie jar
is needed).

Navi's site organizes months by Indian Financial Year (FY "2025-2026" = Apr
2025 .. Mar 2026), selected via a "financial_year" dropdown + a "duration"
(month name) dropdown, POSTed together. One request = one calendar month,
returning that month's list of files across every scheme in a single flat
array (like HDFC's discover, unlike PPFAS's need to scrape an index page).

Format changed over time (confirmed by direct inspection of sample months):
  - FY2019-2020 .. ~FY2021-2022 (the pre-"Navi"-rebrand "Essel Mutual Fund"
    era): ONE workbook per month, many sheets (short codes like "EAF" =
    "Essel Arbitrage Fund"), fund name in row0/col0, columns NOT offset by a
    leading blank column. Different schema entirely from the modern format —
    parse_navi_xlsx.py does not attempt these; they're recorded in the
    manifest (so nothing is silently lost) but download/parse skip them.
  - ~FY2022-2023 onward (post-rebrand "Navi" scheme names): ONE workbook PER
    SCHEME per month — the format parse_navi_xlsx.py targets.
  - 2019 has at least one confirmed instance of the older format actually
    being a .xlsb (Excel binary) file despite an era where most were
    .xlsx/.xls — recorded as-is, not specially handled.

Navi launched/rebranded from Essel Mutual Fund around 2019-2021 (per the
project brief), so the practical floor for useful data is well inside SEBI's
2019 monthly-full-portfolio-XLS mandate era — same floor used by
discover_ppfas_xlsx.py / discover_hdfc_xlsx.py, attempted here too for
completeness (empty months are handled, not fatal).
"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from http_util_navi import fetch_nonce, post_documents

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "navi" / "xlsx_manifest.json"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
CATEGORY_MONTHLY = "884"

EXT_RE = re.compile(r"\.(xlsx?|xlsb)$", re.IGNORECASE)
# Modern titles are like "Navi Flexi Cap Fund 1st – 30th April 2026" or
# "Navi Flexi Cap Fund-April -25" (2025-2026 FY) or "Navi Overnight—Fund"
# (a literal em-dash-as-separator typo confirmed in 2024-2025 FY titles) —
# strip trailing day/date-range and dash-glue defensively rather than one
# fixed pattern, same approach as discover_hdfc_xlsx.py's scheme_name_from_title.
DATE_RANGE_SUFFIX_RE = re.compile(
    r"\s*(\d{1,2}(st|nd|rd|th)?\s*[–—-]\s*)?\d{1,2}(st|nd|rd|th)?\s+"
    r"[A-Za-z]+\.?\s*'?\d{2,4}\s*$"
)
TRAILING_DASH_MONTH_YEAR_RE = re.compile(r"[\s–—-]+[A-Za-z]+\s*[–—-]?\s*'?\d{2,4}\s*$")
GLUE_DASH_RE = re.compile(r"[–—]")


def scheme_name_from_title(title: str) -> str:
    t = EXT_RE.sub("", title.strip())
    t = GLUE_DASH_RE.sub("-", t)
    t = DATE_RANGE_SUFFIX_RE.sub("", t)
    t = TRAILING_DASH_MONTH_YEAR_RE.sub("", t)
    t = re.sub(r"[\s-]+$", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if not t:
        t = title.strip()
    return t


def fy_for(calendar_year: int, month_name: str) -> str:
    """April..December belongs to the FY starting that calendar year;
    January..March belongs to the FY that started the PRIOR calendar year —
    confirmed by direct testing (FY "2026-2027" + "April" -> April 2026
    files; Indian financial-year convention, April-March)."""
    idx = MONTHS.index(month_name)  # 0=Jan .. 11=Dec
    if idx <= 2:  # Jan, Feb, Mar
        return f"{calendar_year - 1}-{calendar_year}"
    return f"{calendar_year}-{calendar_year + 1}"


def fetch_month(nonce: str, calendar_year: int, month_name: str):
    fy = fy_for(calendar_year, month_name)
    try:
        raw = post_documents(nonce, fy, month_name, CATEGORY_MONTHLY, "Monthly")
        payload = json.loads(raw)
    except Exception as ex:
        print(f"  {calendar_year}-{month_name}: FAILED — {ex}")
        return []
    if not payload.get("success"):
        return []
    out = []
    for f in payload.get("data") or []:
        url = f.get("url")
        title = f.get("title") or ""
        if not url:
            continue
        import html as htmllib
        from urllib.parse import urlsplit, urlunsplit, quote
        title = htmllib.unescape(title)
        # A handful of confirmed months (2025-05 onward) return a url containing
        # a literal HTML entity ("&#038;" for "&") and/or unencoded spaces instead
        # of a properly percent-encoded path — curl rejects those outright ("URL
        # malformed"). Unescape then re-quote the path (safe='%' so already-%20
        # sequences aren't double-encoded) before it ever reaches the manifest.
        url = htmllib.unescape(url)
        parts = urlsplit(url)
        url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, parts.fragment))
        out.append({"scheme_name": scheme_name_from_title(title), "url": url, "title": title})
    return out


def main():
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2019
    end_year = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year
    today = date.today()

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    seen = {(e["period"], e["scheme_name"]) for e in manifest}

    nonce = fetch_nonce()
    print(f"Using nonce {nonce}")

    for year in range(start_year, end_year + 1):
        for month_idx, month_name in enumerate(MONTHS, start=1):
            if year == today.year and month_idx > today.month:
                continue
            period = f"{year}-{month_idx:02d}"
            entries = fetch_month(nonce, year, month_name)
            new = 0
            for e in entries:
                key = (period, e["scheme_name"])
                if key in seen:
                    continue
                seen.add(key)
                manifest.append({"period": period, "scheme_name": e["scheme_name"], "url": e["url"], "title": e["title"]})
                new += 1
            print(f"  {period}: {len(entries)} files ({new} new)")
            MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
            time.sleep(0.2)

    periods = sorted(set(e["period"] for e in manifest))
    print(f"\n{len(manifest)} manifest entries across {len(periods)} months "
          f"({periods[0] if periods else '-'} .. {periods[-1] if periods else '-'})")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    sys.exit(main())
