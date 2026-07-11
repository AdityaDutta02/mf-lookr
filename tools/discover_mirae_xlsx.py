#!/usr/bin/env python3
"""List every (period, scheme_name, xlsx_url) in Mirae Asset Mutual Fund's
"Detailed Portfolio Disclosure" archive (Downloads > Portfolio > Monthly
Portfolio on miraeassetmf.co.in — the marketing factsheet PDF at
/downloads/factsheet is a DIFFERENT, unusable source, see tools/README.md
and lib/types.ts's header comment: the factsheet PDF has no ISIN/quantity
per holding, the XLS does).

The listing itself is not server-rendered HTML (confirmed: curl-fetching
/downloads/portfolio returns no file links at all) and not a scraped page
like PPFAS's — it's populated client-side by /DownloadPortfolio.js, which
calls the site's own internal AjaxService JSON API (found by reading
DownloadPortfolio.js + main.js's AjaxService.GetDownloadsDataAsync):

  POST https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData
    body: {"request": {"modulename": "portfolio_tab1", "pgno": 1, "pgsize": N}}

No Referer/Origin/auth needed (confirmed by direct curl testing — unlike
HDFC's Akamai-fronted API, see http_util_hdfc.py). "portfolio_tab1" is the
Monthly Portfolio tab; the endpoint accepts an arbitrarily large pgsize (the
front-end always requests 10 for its own UI pagination, but the server
doesn't cap it) so the entire archive comes back in one call — confirmed:
pgsize=4000 returns all ~3519 rows with DataCount==len(Data), no pagination
loop needed.

Two distinct eras are visible in the titles:
  - 2022-present: one XLSX per scheme per month, title ends "... for <Scheme
    Name>" (or, in ~100 cases, the "for" is simply missing — "<date>
    <Scheme Name>" directly). One sheet per workbook.
  - 2019-2021: one combined workbook per month covering every scheme in a
    single file (title is just "Portfolio Details - <Month> <Year>", no
    scheme name) — same one-sheet-per-scheme-code shape as PPFAS's workbook,
    with an extra SUMMARY sheet mapping scheme code -> name (confirmed by
    downloading and inspecting one). scheme_name is recorded as None for
    these; parse_mirae_xlsx.py's parse_sheet() (shared with the per-scheme
    era, since column layout/positions are identical) iterates every sheet
    and finds each scheme's name itself, same as PPFAS.
"""
import json
import re
import sys
from pathlib import Path

from http_util_mirae import API_URL, SITE_ROOT, post_json

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "mirae" / "xlsx_manifest.json"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_ALT = "|".join(MONTHS.keys())
# "as on 30th June 2026 for Mirae Asset Flexi Cap Fund" / "as on 31st January, 2023 for ..."
# / "as on 30th April 2025 Mirae Asset ..." (no "for") / "as on 28 February, 2022 for ..."
TITLE_RE = re.compile(
    rf"as\s+on\s+\d{{1,2}}(?:st|nd|rd|th)?\.?\s*({MONTH_ALT})\.?,?\s*(\d{{4}})\s*(?:for\s+)?(.*)$",
    re.IGNORECASE,
)
# "Portfolio Details - July 2021" / "Portfolio Details - August 2020."  (combined-era, no scheme)
COMBINED_RE = re.compile(rf"portfolio\s+details\s*-\s*({MONTH_ALT})\.?\s*(\d{{4}})\.?\s*$", re.IGNORECASE)


def parse_title(title: str):
    """Returns (period, scheme_name) or (None, None) if the title can't be read.
    scheme_name is None for combined-workbook-era entries (see module docstring)."""
    t = re.sub(r"\s+", " ", title).strip()
    m = TITLE_RE.search(t)
    if m:
        mon, yr, rest = m.group(1).lower(), m.group(2), m.group(3).strip()
        period = f"{yr}-{MONTHS[mon]:02d}"
        return period, (rest or None)
    m = COMBINED_RE.search(t)
    if m:
        mon, yr = m.group(1).lower(), m.group(2)
        return f"{yr}-{MONTHS[mon]:02d}", None
    return None, None


def full_url(url: str) -> str:
    if url.startswith("http"):
        return url
    # The source API returns most relative URLs leading-slashed ("/docs/...") but
    # occasionally drops the slash entirely ("docs/..." — confirmed by direct
    # inspection, e.g. the March 2026 Nifty PSU Bank ETF entry) — normalize so a
    # straight concat with SITE_ROOT never produces "...co.indocs/...".
    return SITE_ROOT + ("" if url.startswith("/") else "/") + url


def main():
    print("Fetching full Monthly Portfolio manifest from AjaxService (single request)...")
    raw = post_json(API_URL, {"request": {"modulename": "portfolio_tab1", "pgno": 1, "pgsize": 4000}})
    payload = json.loads(raw)
    if payload.get("ReturnCode") != "0":
        print(f"API returned ReturnCode={payload.get('ReturnCode')} msg={payload.get('ReturnMsg')}")
        return 1
    rows = payload.get("Data") or []
    data_count = payload.get("DataCount")
    print(f"DataCount={data_count}, rows returned={len(rows)}")

    entries = []
    unparsed = []
    for r in rows:
        title = r.get("Title") or ""
        url = r.get("URL") or ""
        if not url:
            continue
        period, scheme_name = parse_title(title)
        if not period:
            unparsed.append(title)
            continue
        entries.append({
            "period": period,
            "scheme_name": scheme_name,
            "url": full_url(url),
            "title": title.strip(),
        })

    entries.sort(key=lambda e: (e["period"], e["scheme_name"] or ""))
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(entries, indent=2))

    periods = sorted(set(e["period"] for e in entries))
    per_scheme = sum(1 for e in entries if e["scheme_name"])
    combined = sum(1 for e in entries if not e["scheme_name"])
    print(f"\n{len(entries)} manifest entries across {len(periods)} months "
          f"({periods[0] if periods else '-'} .. {periods[-1] if periods else '-'})")
    print(f"  {per_scheme} per-scheme-file entries, {combined} combined-workbook entries")
    print(f"Manifest written to {MANIFEST_PATH}")
    if unparsed:
        print(f"\n{len(unparsed)} titles could not be parsed for period (skipped):")
        for t in unparsed[:20]:
            print("  -", t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
