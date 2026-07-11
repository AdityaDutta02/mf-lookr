#!/usr/bin/env python3
"""List every (period, scheme_title, xlsx_url) in SBI Mutual Fund's "Detailed
Portfolio Disclosure" archive, via the JSON/HTML endpoint the site's own
/portfolios page uses (no bot-protection encountered — plain UA + JSON
Content-Type is enough, confirmed by direct testing; unlike HDFC's Akamai
front no Origin/Referer header is required).

POST https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets
  JSON body: {"FundId": 0, "PSYear": "<YYYY>", "PSMonth": "<Month name>",
              "PSFrequency": "Monthly"}
FundId: 0 means "every scheme" — one call per (year, month) returns every
scheme's file for that month as an HTML <table> fragment (not JSON), same
"one month, one call, every scheme" shape as HDFC's API.

/portfolios' own dropdown goes back to 2013, but SEBI's monthly full-
portfolio-XLS mandate only reliably starts 2019 (see discover_ppfas_xlsx.py,
discover_hdfc_xlsx.py) — 2019 is the floor here too; earlier years are
attempted anyway since a failed/empty month costs one extra call and never
raises.

The row also includes a synthetic "All Schemes Monthly Portfolio" combined
workbook — skipped (own separate download would fight one-workbook-per-
scheme's dedup logic; per-scheme files are the deterministic unit here).

The <title> text (e.g. "SBI Arbitrage Opportunities Fund MONTHLY PORTFOLIO -
MAY 2026" for recent months, "SBI ARBITRAGE OPPORTUNITIES FUND PORTFOLIO"
ALL-CAPS with no date suffix for 2019-era months) is ONLY used to build a
filesystem-safe slug for the download path — never trusted as the scheme's
canonical name. The canonical name comes from inside the xlsx itself (the
"SCHEME NAME :" cell), read by parse_sbi_xlsx.py — same "identity lives in
the file, not the link text" principle HDFC's toolkit already established.
"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from http_util_sbi import post_json

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "sbi" / "xlsx_manifest.json"

API_URL = "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets"
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

ROW_RE = re.compile(
    r'<td><a href="([^"]+)"\s+target="_blank">([^<]+)</a></td>', re.IGNORECASE
)
ALL_SCHEMES_RE = re.compile(r"^all schemes", re.IGNORECASE)
SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-")


def fetch_month(year: int, month_name: str):
    """Returns list of {title, url} for one (year, month), or [] on any
    failure / empty month — never raises, mirrors discover_hdfc_xlsx.py's
    fetch_month() contract."""
    body = json.dumps({"FundId": 0, "PSYear": str(year), "PSMonth": month_name, "PSFrequency": "Monthly"})
    try:
        html = post_json(API_URL, body)
    except Exception as ex:
        print(f"  {year}-{month_name}: FAILED — {ex}")
        return []

    out = []
    for url, title in ROW_RE.findall(html):
        title = title.strip()
        if ALL_SCHEMES_RE.match(title):
            continue
        out.append({"title": title, "url": url})
    return out


def main():
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2019
    end_year = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year
    today = date.today()

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    seen = {(e["period"], e["title"]) for e in manifest}

    for year in range(start_year, end_year + 1):
        for m_idx, month_name in enumerate(MONTH_NAMES, start=1):
            if year == today.year and m_idx > today.month:
                continue
            period = f"{year}-{m_idx:02d}"
            entries = fetch_month(year, month_name)
            new = 0
            for e in entries:
                key = (period, e["title"])
                if key in seen:
                    continue
                seen.add(key)
                manifest.append({"period": period, "title": e["title"], "url": e["url"], "scheme_slug": slug(e["title"])})
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
