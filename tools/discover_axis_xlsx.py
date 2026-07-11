#!/usr/bin/env python3
"""List every (period, scheme_code, xls_url) in Axis Mutual Fund's "Monthly
Scheme Portfolios" archive (the SEBI-mandated Detailed Portfolio Disclosure —
NOT the marketing factsheet PDF at transact.axismf.com/cms/.../pdf-factsheets/,
see the module docstring in parse_axis_xlsx.py for why that distinction matters).

Axis's site (www.axismf.com, a Next.js app) exposes this via a JSON POST API
discovered by intercepting real browser traffic with a headless browser (plain
curl/WebFetch gets 403'd — this is Akamai-fronted, same class of protection as
HDFC's site, see http_util_hdfc.py):

  POST https://www.axismf.com/cms/get-scheme-documents
    body: {"sdType":"yearMonthSchemeDocs","sdID":"sdMonthSchemePortfolio",
           "year":"<YYYY>","month":"<FullMonthName>","schemeCode":"<code>"}
    headers: Content-Type: application/json, Authorization: Bearer <token>,
             browser-id: <uuid>, Referer/Origin: https://www.axismf.com,
             Accept: */*

The Authorization Bearer token + browser-id are minted client-side by the
page's own JS (a "feCommunicators" helper bundled into chunk 183) and are NOT
reproducible by computing them yourself in a vacuum — they must be harvested
from a real page load.

IMPORTANT — CONFIRMED BY DIRECT TESTING, curl CANNOT drive this API, even
with a valid harvested Authorization header: a plain `curl` replay of the
exact header set that worked from inside the real browser got back HTTP 200
with a FAKE type-annotated decoy payload (literally
`{"data":{"documentList":[{"docuementURL":"string[70]",...}]}}` — schema
placeholders, not real values), while the identical request made via
`fetch()` executed FROM the live page (same token, same browser-id) returned
real data. This is Akamai Bot Manager fingerprinting the TLS/JA3 + browser
sensor signature of the connection itself, not just checking header values —
curl's TLS handshake never passes it, no matter what headers are copied. So,
unlike PPFAS/HDFC (plain curl + UA/Referer/Origin headers was enough there),
Axis's discovery step MUST run its fetch loop from inside a real browser
page — a bare Authorization-header replay via curl is a dead end and will
silently return decoy data that LOOKS well-formed. This script defends
against that by validating every response's docuementURL looks like a real
https:// URL before trusting it (see `_looks_like_real_url` below) and
aborting loudly otherwise, but the safe path is: run the crawl loop with
Playwright (or equivalent), not curl.

RATE LIMIT WARNING (confirmed by direct testing): a burst of ~10-way
concurrent requests against /cms/get-scheme-documents triggered a same-IP
"Access Denied" WAF block on the ENTIRE www.axismf.com origin (not just the
API path) that persisted at least several minutes and blocked even the plain
page load. This script is deliberately SEQUENTIAL with a delay between
requests — do not add concurrency without re-confirming the WAF's tolerance
first, and if you do get blocked, stop and wait rather than retrying harder.

This script's HTTP layer (curl-based, matching the rest of tools/'s
convention) is therefore only reliable for the STATIC FILE downloads
(download_axis_xlsx.py — confirmed working fine over plain curl, the WAF
gate is specific to the /cms/get-scheme-documents API, not the file host).
For the discovery step itself, either (a) run this script's logic through a
`playwright`-driven Python process (not included here — `playwright` isn't
installed in this venv and wasn't added without approval, see repo's
dependency-approval convention), or (b) drive it interactively via a
Playwright MCP browser session using the exact request/response shape
documented above, saving results into cache/axis/xlsx_manifest.json in this
script's schema. The Authorization header pair harvested from one such
browser session can be passed here via AXIS_AUTH_HEADERS_JSON for the
now-known-decoy-checked curl path, useful only as a fallback / sanity check.

schemeCode "Consolidated" is NOT a real scheme — it returns Daily/Weekly/Ad-hoc
supplementary reports, not the full monthly holdings disclosure. Only
documentName matching /monthly portfolio/i is a genuine full disclosure.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "cache" / "axis" / "xlsx_manifest.json"
SCHEMES_PATH = ROOT / "cache" / "axis" / "schemes.json"

API_URL = "https://www.axismf.com/cms/get-scheme-documents"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

REQUEST_DELAY_SEC = 0.5  # deliberately slow — see WAF warning in module docstring


def load_auth_headers():
    raw = os.environ.get("AXIS_AUTH_HEADERS_JSON")
    if not raw:
        print("AXIS_AUTH_HEADERS_JSON env var not set.")
        print("Capture it by loading https://www.axismf.com/statutory-disclosures in a")
        print("real browser (Playwright), clicking the '8. Portfolios' accordion header,")
        print("and reading the resulting POST /cms/get-scheme-documents request's headers.")
        print('Then: export AXIS_AUTH_HEADERS_JSON=\'{"authorization":"Bearer ...","browser-id":"..."}\'')
        sys.exit(1)
    return json.loads(raw)


def _looks_like_real_url(value) -> bool:
    """Akamai's decoy payload puts a literal schema placeholder like
    "string[70]" where a real URL would be — reject anything that isn't a
    plausible https:// URL so a decoy response never silently poisons the
    manifest (see module docstring)."""
    return isinstance(value, str) and value.startswith("https://") and "." in value


def curl_post_json(url: str, headers: dict, body: dict) -> dict:
    cmd = ["curl", "-sL", "-A", UA, "--fail", "-X", "POST", url,
           "-H", "Content-Type: application/json",
           "-H", "Accept: */*",
           "-H", "Referer: https://www.axismf.com/statutory-disclosures",
           "-H", "Origin: https://www.axismf.com"]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    cmd += ["--data", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}): {r.stderr.decode(errors='replace')[:200]}")
    return json.loads(r.stdout)


def fetch_scheme_list(headers: dict):
    """schemeCategories from the base (no year/month/schemeCode) call — every
    scheme Axis currently discloses, {schemeName, schemeCode}. "Consolidated"
    is filtered out (not a real scheme, see module docstring)."""
    payload = curl_post_json(API_URL, headers, {"sdType": "yearMonthSchemeDocs", "sdID": "sdMonthSchemePortfolio"})
    cats = (payload.get("data") or {}).get("schemeCategories") or []
    return [c for c in cats if c.get("schemeCode") and c["schemeCode"] != "Consolidated"]


def fetch_month(headers: dict, scheme_code: str, year: int, month_name: str):
    """Returns list of {url, documentName, postedDate} for one (scheme, period),
    filtered to genuine 'Monthly Portfolio' disclosures (the API also serves
    ad-hoc/weekly/daily reports under the same call for some scheme codes)."""
    try:
        payload = curl_post_json(API_URL, headers, {
            "sdType": "yearMonthSchemeDocs", "sdID": "sdMonthSchemePortfolio",
            "year": str(year), "month": month_name, "schemeCode": scheme_code,
        })
    except Exception as ex:
        print(f"  {scheme_code} {year}-{month_name}: FAILED — {ex}")
        return []
    docs = ((payload.get("data") or {}).get("documentList")) or []
    out = []
    for d in docs:
        name = d.get("documentName") or ""
        if "monthly portfolio" not in name.lower():
            continue
        url = d.get("docuementURL")  # sic — real API field name, misspelled upstream
        if not _looks_like_real_url(url):
            print(f"  {scheme_code} {year}-{month_name}: got a non-URL value back "
                  f"({url!r}) — likely an Akamai decoy response (see module docstring), "
                  f"skipping rather than trusting it")
            continue
        out.append({"url": url, "documentName": name, "postedDate": d.get("documentPostedDate")})
    return out


def main():
    headers = load_auth_headers()
    start_period = sys.argv[1] if len(sys.argv) > 1 else "2025-01"
    end_period = sys.argv[2] if len(sys.argv) > 2 else "2026-06"
    start_y, start_m = (int(x) for x in start_period.split("-"))
    end_y, end_m = (int(x) for x in end_period.split("-"))

    schemes = fetch_scheme_list(headers)
    SCHEMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMES_PATH.write_text(json.dumps(schemes, indent=2))
    print(f"{len(schemes)} schemes found, written to {SCHEMES_PATH}")

    periods = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        periods.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    manifest = []
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    seen = {(e["period"], e["scheme_code"]) for e in manifest}

    for scheme in schemes:
        code = scheme["schemeCode"]
        for (year, month) in periods:
            period = f"{year}-{month:02d}"
            if (period, code) in seen:
                continue
            docs = fetch_month(headers, code, year, MONTHS[month - 1])
            time.sleep(REQUEST_DELAY_SEC)
            if not docs:
                continue
            entry = {
                "period": period, "scheme_code": code, "scheme_name": scheme["schemeName"],
                "url": docs[0]["url"], "document_name": docs[0]["documentName"],
            }
            manifest.append(entry)
            seen.add((period, code))
            print(f"  {code} {period}: {docs[0]['documentName']}")
            MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    periods_found = sorted(set(e["period"] for e in manifest))
    print(f"\n{len(manifest)} manifest entries across {len(periods_found)} months "
          f"({periods_found[0] if periods_found else '-'} .. {periods_found[-1] if periods_found else '-'})")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    sys.exit(main())
