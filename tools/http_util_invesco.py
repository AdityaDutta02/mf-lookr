"""Invesco-specific HTTP helpers. Separate from http_util.py (PPFAS's) and
http_util_hdfc.py (HDFC's) for the same reason each of those is separate —
avoid touching a shared helper another AMC's working pipeline depends on.

Invesco's site (invescomutualfund.com) isn't Akamai-fronted the way HDFC's
is — plain UA + Referer is enough, no Origin header needed (confirmed by
direct testing: no 403/CORS-Forbidden without it). Still shells out to curl
instead of urllib for the same reason http_util.py does: the macOS
python.org framework build's local cert store is broken for urllib/ssl;
curl uses the system trust store correctly.
"""
import os
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
REFERER = "https://invescomutualfund.com/literature-and-form?tab=Complete"


def fetch_json(url: str, timeout: int = 60) -> bytes:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "-H", f"Referer: {REFERER}", "--fail", url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


def download_file(url: str, dest_path: str, timeout: int = 120) -> int:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "-H", f"Referer: {REFERER}", "--fail", "-o", dest_path, url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return os.path.getsize(dest_path)
