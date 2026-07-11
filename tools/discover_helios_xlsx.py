#!/usr/bin/env python3
"""List every (period, scheme_name, xlsx_url) in Helios Mutual Fund's "Monthly
Portfolio" section of https://www.heliosmf.in/portfolio-disclosure/ — the
SEBI-mandated monthly "Detailed Portfolio Disclosure" XLSX, NOT the marketing
factsheet PDF under the site's "Factsheets" tab (same PDF-vs-XLS trap as
PPFAS/HDFC — see parse_helios_xlsx.py docstring).

Helios is a very new AMC (schemes launched from Oct 2023 onward) so the
archive is short — a year or two, not a decade. That's expected, not a bug.

No bot-protection encountered: a plain curl (see http_util.py) fetches the
fully server-rendered page, all download links included statically (unlike
some sites, no JS/AJAX call is needed — confirmed by diffing a curl fetch
against a Playwright-rendered DOM snapshot before writing this).

The page's "Portfolio Disclosures" tab has THREE accordions — Fortnightly
Portfolio (Overnight Fund only), Monthly Portfolio (all schemes — what we
want), Half Yearly Portfolio (discontinued w.e.f. April 2026, not our
source). The whole tablist markup is duplicated verbatim in the raw HTML
(a responsive desktop/mobile pair) — we only walk the FIRST "Monthly
Portfolio" block's scheme headings and de-dupe the resulting manifest by
(scheme_name, period) so the duplicate copy is harmless.

A handful of older (2023-2024) filenames don't carry the scheme name in the
filename itself (e.g. "HeliosMF_Monthly-Portfolio_31st-October-2023.xls") —
scheme identity can't be recovered from the URL text alone for those, so we
determine it from DOM position (which scheme's <h5> heading the link's HTML
chunk falls under) instead of the filename, which is robust to that.
"""
import json
import re
import sys
from pathlib import Path

from http_util import fetch_text

PAGE_URL = "https://www.heliosmf.in/portfolio-disclosure/"

# Canonical scheme names as they appear in the "Monthly Portfolio" accordion's
# own <h5> headings, in the order the site lists them.
SCHEME_HEADINGS = [
    "Helios Small Cap Fund",
    "Helios Overnight Fund",
    "Helios Flexi Cap Fund",
    "Helios Balanced Advantage Fund",
    "Helios Financial Services Fund",
    "Helios Large &amp; Mid Cap Fund",
    "Helios Mid Cap Fund",
    "Helios Arbitrage Fund",
]

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
# Trailing "<day><st|nd|rd|th>-<Month>-<Year>" right before the extension (allowing an
# odd stray "-1" disambiguator suffix some re-uploads carry, e.g. "...-March-2024-1.xls").
DATE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?-([A-Za-z]+)-(\d{4})(?:-\d+)?\.xlsx?(?:\?.*)?$", re.IGNORECASE
)
LINK_RE = re.compile(r'href="(https://www\.heliosmf\.in/wp-content/uploads/[^"]+?\.xlsx?)"', re.IGNORECASE)
H5_RE = re.compile(r"<h5[^>]*>(.*?)</h5>", re.DOTALL)


def infer_period(url: str):
    m = DATE_RE.search(url)
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower())
    if not month:
        return None
    return f"{m.group(3)}-{month:02d}"


def clean_heading(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).strip()


def main():
    html = fetch_text(PAGE_URL)

    # Locate the FIRST "Monthly Portfolio" heading, then walk headings after it
    # until we hit one that isn't a known scheme name (that's "Half Yearly
    # Portfolio", the next accordion) — gives us 8 (scheme, chunk_start) pairs.
    headings = list(H5_RE.finditer(html))
    monthly_idx = next(i for i, m in enumerate(headings) if clean_heading(m.group(1)) == "Monthly Portfolio")

    # Within a scheme's accordion, download links are further grouped under
    # per-year sub-headings ("2026", "2025", ...) — also <h5> tags, interleaved
    # with the scheme headings themselves. Skip those; stop entirely once we
    # reach "Half Yearly Portfolio" (the next accordion, a hard boundary).
    known_schemes = {clean_heading(h) for h in SCHEME_HEADINGS}
    scheme_positions = []  # (scheme_name, chunk_start_pos)
    monthly_block_end = len(html)  # fallback if "Half Yearly Portfolio" is never found
    for m in headings[monthly_idx + 1:]:
        text = clean_heading(m.group(1))
        if text == "Half Yearly Portfolio":
            monthly_block_end = m.start()  # closes the LAST scheme's chunk — without this
            # the last scheme's links regex would run off the end of the Monthly Portfolio
            # accordion into the page's duplicate desktop/mobile copy of the whole tablist,
            # silently stealing every other scheme's links into the last scheme's bucket.
            break
        if text in known_schemes:
            scheme_positions.append((text.replace("&amp;", "&"), m.end()))

    if len(scheme_positions) != len(SCHEME_HEADINGS):
        print(f"WARNING: expected {len(SCHEME_HEADINGS)} scheme headings under Monthly "
              f"Portfolio, found {len(scheme_positions)} — site markup may have changed.")

    entries = {}  # (scheme_name, period) -> url
    for i, (scheme_name, start) in enumerate(scheme_positions):
        end = scheme_positions[i + 1][1] if i + 1 < len(scheme_positions) else monthly_block_end
        chunk = html[start:end]
        for url in LINK_RE.findall(chunk):
            period = infer_period(url)
            if not period:
                print(f"  skip (no date parsed): {url}")
                continue
            entries.setdefault((scheme_name, period), url)

    out = [{"scheme_name": s, "period": p, "url": u} for (s, p), u in sorted(entries.items())]
    out_path = Path(__file__).parent / "cache" / "helios" / "xlsx_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))

    by_scheme = {}
    for e in out:
        by_scheme.setdefault(e["scheme_name"], []).append(e["period"])
    for scheme, periods in by_scheme.items():
        periods.sort()
        print(f"  {scheme}: {len(periods)} months, {periods[0]} .. {periods[-1]}")
    print(f"\n{len(out)} (scheme, period) entries across {len(by_scheme)} schemes.")
    print(f"Manifest written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
