"""Navi-specific HTTP helpers. Separate from http_util.py (PPFAS's) and
http_util_hdfc.py because Navi's portfolio-disclosure list is a WordPress REST
route (nv/v1/documents) that needs a WP-NONCE header — plain curl without it
gets a 401/403 from the WP REST layer (confirmed by direct testing). The nonce
is generated per page-load via wp_create_nonce() but is NOT tied to a session
cookie in practice — a fresh GET of the portfolio page yields a nonce that
works for POSTs made without sending any cookies back (confirmed by direct
testing), so no cookie jar is needed, just a fresh nonce fetched once per run.

Shells out to curl (not urllib) for the same reason http_util.py does: the
macOS python.org framework build's local cert store is broken for urllib/ssl;
curl uses the system trust store correctly.
"""
import re
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PORTFOLIO_PAGE = "https://navi.com/mutual-fund/downloads/portfolio"
REST_URL = "https://navi.com/wp-json/nv/v1/documents"
NONCE_RE = re.compile(r'"nonce":"([a-f0-9]+)"')


def fetch_text(url: str) -> str:
    r = subprocess.run(["curl", "-sL", "-A", UA, "--fail", url], capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def fetch_nonce() -> str:
    html = fetch_text(PORTFOLIO_PAGE)
    m = NONCE_RE.search(html)
    if not m:
        raise RuntimeError("Could not find navi_property.nonce in portfolio page HTML")
    return m.group(1)


def post_documents(nonce: str, financial_year: str, value: str, category: str,
                    doc_type: str, order: str = "DESC", timeout: int = 60) -> str:
    """POST to the nv/v1/documents WP REST route and return the raw JSON text.
    category is the WP taxonomy term id for the relevant tab — "884" is
    Monthly Portfolio (confirmed by inspecting the page's
    data-category="884" data-type="Monthly" dropdown-content-select block;
    885=Fortnightly, 886=HalfYearly, 887=Quarterly, 928=Portfolio Overlap —
    only 884/Monthly is used here, the SEBI-mandated one)."""
    cmd = [
        "curl", "-sL", "-A", UA, "--fail",
        "-H", f"WP-NONCE: {nonce}",
        "-H", f"Referer: {PORTFOLIO_PAGE}",
        "-X", "POST", REST_URL,
        "--data-urlencode", f"financial_year={financial_year}",
        "--data-urlencode", f"value={value}",
        "--data-urlencode", f"category={category}",
        "--data-urlencode", f"type={doc_type}",
        "--data-urlencode", f"order={order}",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for documents POST: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def download_file(url: str, dest_path: str, timeout: int = 120) -> int:
    r = subprocess.run(["curl", "-sL", "-A", UA, "--fail", "-o", dest_path, url], capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    return os.path.getsize(dest_path)
