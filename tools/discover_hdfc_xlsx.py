#!/usr/bin/env python3
"""List every (period, scheme_name, xlsx_url) in HDFC Mutual Fund's "Detailed
Portfolio Disclosure" archive, via the JSON API HDFC's site itself uses
(no HTML scraping needed, unlike PPFAS — see discover_ppfas_xlsx.py).

POST https://cms.hdfcfund.com/en/hdfc/api/v2/disclosures/monthfortportfolio
  multipart form: year=<YYYY>, type=monthly, month=<1-12>
Requires UA + Referer + Origin headers or Akamai returns 403 ("CORS Forbidden:
Origin Not Found") — confirmed by direct testing; Origin is the part PPFAS's
shared http_util.py doesn't send, hence the separate http_util_hdfc.py helper.

One month's response lists every scheme's file in a single flat array — no
need to enumerate schemes separately. 2019 is the floor for the same reason
noted in discover_ppfas_xlsx.py (SEBI's monthly full-portfolio-XLS mandate
era); earlier years are attempted too but expected to come back empty.
"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from http_util_hdfc import post_form_json

API_URL = "https://cms.hdfcfund.com/en/hdfc/api/v2/disclosures/monthfortportfolio"
ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "hdfc" / "xlsx_manifest.json"

# Recent titles: "Monthly HDFC <Scheme Name> - <DD Month YYYY>.xlsx". Older
# (2021-2022 era) titles are messier — no "Monthly " prefix, a doubled "HDFC HDFC"
# lead-in, inconsistent date-suffix spacing ("30 April2022", "- Monthly 31 October
# 2022"), sometimes no date suffix at all, sometimes ALL CAPS — confirmed by
# inspecting the actual manifest. Strip defensively instead of one fixed pattern.
EXT_RE = re.compile(r"\.xlsx?$", re.IGNORECASE)
MONTHLY_PREFIX_RE = re.compile(r"^Monthly\s+", re.IGNORECASE)
DATE_SUFFIX_RE = re.compile(r"\s*-\s*(Monthly\s+)?\d{1,2}\s*[A-Za-z]+\.?\s*\d{4}\s*$", re.IGNORECASE)
DUP_HDFC_RE = re.compile(r"^(HDFC)\s+\1\b", re.IGNORECASE)
LEADING_HDFC_RE = re.compile(r"^HDFC\b", re.IGNORECASE)


def scheme_name_from_title(title: str) -> str:
    t = EXT_RE.sub("", title.strip())
    t = MONTHLY_PREFIX_RE.sub("", t)
    t = DATE_SUFFIX_RE.sub("", t)
    t = DUP_HDFC_RE.sub(r"\1", t)
    t = t.strip()
    if not LEADING_HDFC_RE.match(t):
        t = f"HDFC {t}"
    return t


def fetch_month(year: int, month: int):
    """Returns list of {scheme_name, url, file_id} for one (year, month), or
    [] if the month has no data / the request fails — never raises, so one
    bad month doesn't kill the whole discovery run."""
    try:
        raw = post_form_json(API_URL, {"year": year, "type": "monthly", "month": month})
        payload = json.loads(raw)
    except Exception as ex:
        print(f"  {year}-{month:02d}: FAILED — {ex}")
        return []
    data = payload.get("data") or {}
    files = data.get("files") or []
    out = []
    for f in files:
        url = (f.get("file") or {}).get("url")
        title = f.get("title") or ""
        if not url:
            continue
        out.append({"scheme_name": scheme_name_from_title(title), "url": url, "file_id": f.get("file_id"), "title": title})
    return out


def main():
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2019
    end_year = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year
    today = date.today()

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    seen = {(e["period"], e["scheme_name"]) for e in manifest}

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == today.year and month > today.month:
                continue
            period = f"{year}-{month:02d}"
            entries = fetch_month(year, month)
            new = 0
            for e in entries:
                key = (period, e["scheme_name"])
                if key in seen:
                    continue
                seen.add(key)
                manifest.append({"period": period, "scheme_name": e["scheme_name"], "url": e["url"], "file_id": e["file_id"]})
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
