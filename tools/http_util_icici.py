"""ICICI-specific HTTP helpers. Separate from http_util.py (PPFAS's) and
http_util_hdfc.py (HDFC's) because ICICI's API gateway (apimf.icicipruamc.com)
needs its own quirky combination of headers.

Two distinct quirks, confirmed by direct testing:

1. The JSON API (apimf.icicipruamc.com/nms/v1/...) requires a plain, undocumented
   "env: api" header in addition to Referer/Origin — without it the edge returns
   HTTP 200 but with a *text* body reading "Original Status Code: 404 Original
   Response: <html>..." (i.e. it silently swaps in the site's own SPA 404 page
   while still claiming success at the transport layer). No UA/Referer variation
   fixes this; only "env: api" does.

2. The actual file *download* links returned by that API 307-redirect from
   www.icicipruamc.com to archive.icicipruamc.com — which has NO DNS record at
   all (confirmed via three independent resolvers: system, Cloudflare DoH, and
   a real Chromium instance navigating there directly — all fail identically,
   "could not resolve host"). This is a genuine site-side bug on ICICI's
   deployment, not a bot-protection measure. The fix: every file the API returns
   under "/downloads/Files/..." is ALSO reachable directly on www.icicipruamc.com
   by prefixing the path with "/blob" (e.g. "/blob/downloads/Files/...") — this
   route serves straight from the underlying Azure Blob Storage origin and
   bypasses the broken archive.icicipruamc.com redirect entirely. Discovered by
   grepping the site's own main.*.chunk.js for other "/blob/..." asset URLs it
   uses for banners/PDFs elsewhere on the same site, then confirming the same
   prefix works for portfolio-disclosure files too.

Shells out to curl (not urllib) for the same reason the other AMCs' helpers do:
the macOS python.org framework build's local cert store is broken for
urllib/ssl; curl uses the system trust store correctly.
"""
import subprocess
from urllib.parse import quote

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
REFERER = "https://www.icicipruamc.com/"
ORIGIN = "https://www.icicipruamc.com"
API_BASE = "https://apimf.icicipruamc.com"
FILE_BASE = "https://www.icicipruamc.com/blob"  # see quirk #2 above


def post_json(url: str, payload: str, timeout: int = 30) -> str:
    r = subprocess.run(
        ["curl", "-s", "-A", UA, "-H", f"Referer: {REFERER}", "-H", f"Origin: {ORIGIN}",
         "-H", "env: api", "-H", "Content-Type: application/json",
         "-d", payload, url, "--max-time", str(timeout)],
        capture_output=True, timeout=timeout + 10,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def get_json(url: str, timeout: int = 30) -> str:
    r = subprocess.run(
        ["curl", "-s", "-A", UA, "-H", f"Referer: {REFERER}", "-H", f"Origin: {ORIGIN}",
         "-H", "env: api", url, "--max-time", str(timeout)],
        capture_output=True, timeout=timeout + 10,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def download_file(relative_path: str, dest_path: str, timeout: int = 120) -> int:
    """relative_path is the API's raw "url" field, e.g.
    "/downloads/Files/Monthly Portfolio Disclosures/2026/June/Monthly-Portfolio-Disclosure-June-2026.zip"
    — NOT url-encoded, may contain spaces/parens. We prefix with FILE_BASE
    ("/blob") to route around the broken archive.icicipruamc.com redirect."""
    # relative_path arrives raw from the API (spaces, parens, unescaped) — quote
    # it (keeping "/" as a separator) before handing to curl, which otherwise
    # rejects the URL outright ("curl: (3) URL using bad/illegal format").
    url = FILE_BASE + quote(relative_path, safe="/")
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "-H", f"Referer: {REFERER}", "--fail", "-o", dest_path, url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    return os.path.getsize(dest_path)
