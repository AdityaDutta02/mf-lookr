"""HDFC-specific HTTP helpers. Separate from http_util.py (PPFAS's, untouched)
because HDFC's Akamai-fronted API needs an Origin header in addition to UA +
Referer — plain "curl -A ... -H Referer" alone gets "CORS Forbidden: Origin Not
Found" (confirmed by direct testing). PPFAS's helper doesn't send Origin at all,
so we don't touch it — a shared helper risks breaking that working path.

Also shells out to curl (not urllib) for the same reason http_util.py does:
the macOS python.org framework build's local cert store is broken for
urllib/ssl; curl uses the system trust store correctly.
"""
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
REFERER = "https://www.hdfcfund.com/"
ORIGIN = "https://www.hdfcfund.com"


def post_form_json(url: str, fields: dict, timeout: int = 60) -> bytes:
    """POST multipart/form-data (curl -F per field) and return raw response bytes."""
    cmd = ["curl", "-sL", "-A", UA, "-H", f"Referer: {REFERER}", "-H", f"Origin: {ORIGIN}", "--fail", "-X", "POST", url]
    for k, v in fields.items():
        cmd += ["-F", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url} fields={fields}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


def download_file(url: str, dest_path: str, timeout: int = 120) -> int:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "-H", f"Referer: {REFERER}", "-H", f"Origin: {ORIGIN}", "--fail", "-o", dest_path, url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    return os.path.getsize(dest_path)
