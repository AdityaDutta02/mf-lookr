"""Mirae-specific HTTP helpers. Separate from http_util.py (PPFAS's, untouched)
because Mirae's discovery source isn't a scraped HTML page (like PPFAS) or a
multipart-form POST (like HDFC) — it's a JSON POST to an internal AjaxService
endpoint the site's own front-end JS calls (see DownloadPortfolio.js / main.js's
AjaxService.GetDownloadsDataAsync -> POST /AjaxService/GetDownloadsData, body
{"request":{"modulename":"portfolio_tab1","pgno":1,"pgsize":N}}). Confirmed by
direct testing: no Referer/Origin header is required (unlike HDFC's Akamai-fronted
API), a plain UA is enough.

Also shells out to curl (not urllib), matching http_util.py's rationale: the
macOS python.org framework build's local cert store is broken for urllib/ssl;
curl uses the system trust store correctly.
"""
import json
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
API_URL = "https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData"
SITE_ROOT = "https://www.miraeassetmf.co.in"


def post_json(url: str, payload: dict, timeout: int = 60) -> bytes:
    cmd = [
        "curl", "-sL", "-A", UA,
        "-H", "Content-Type: application/json;charset=utf-8",
        "--fail", "-X", "POST", url,
        "-d", json.dumps(payload),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


def download_file(url: str, dest_path: str, timeout: int = 120) -> int:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "--fail", "-o", dest_path, url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    return os.path.getsize(dest_path)
