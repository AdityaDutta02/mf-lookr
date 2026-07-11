"""SBI-specific HTTP helpers. Separate module (not http_util.py, PPFAS's,
untouched) purely for naming-convention consistency with http_util_hdfc.py —
SBI's site has NO bot-protection at all, confirmed by direct testing: plain
UA + JSON Content-Type is enough, no Origin/Referer/token needed (unlike
HDFC's Akamai-fronted API).

Shells out to curl (not urllib) for the same reason http_util.py does: the
macOS python.org framework build's local cert store is broken for
urllib/ssl; curl uses the system trust store correctly.

SBI-specific quirk (confirmed by direct testing): scheme titles/URLs with an
apostrophe (e.g. "SBI Children's Benefit Fund") come back from
GetSchemePortfolioSheets with the LITERAL HTML entity text "&#39;" left
un-decoded inside the href itself — not a real apostrophe, and not a decoded
one either. Requesting that raw entity text as part of the URL path gets
rejected outright by SBI's own WAF ("Request Rejected... support ID...",
HTTP 200 with an HTML error body, not a real failure status — so it must be
caught by content, not status code). html.unescape() before every request
fixes it: the WAF accepts a literal apostrophe in the path just fine.
"""
import html
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def post_json(url: str, payload: str, timeout: int = 60) -> str:
    """POST a raw JSON string body, return the response as decoded text
    (SBI's portfolio-sheets endpoint returns an HTML table fragment, not
    JSON, despite the JSON request body — dataType: "html" in Portfolios.js)."""
    r = subprocess.run(
        [
            "curl", "-sL", "-A", UA,
            "-H", "Content-Type: application/json;charset=utf-8",
            "--fail", "-X", "POST", url, "-d", payload,
        ],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def download_file(url: str, dest_path: str, timeout: int = 120) -> int:
    url = html.unescape(url)  # see module docstring — un-decoded "&#39;" etc. trips SBI's WAF
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "--fail", "-o", dest_path, url],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    size = os.path.getsize(dest_path)
    # WAF rejections come back as HTTP 200 with an HTML error body, not a curl
    # failure — --fail alone doesn't catch this, so sniff the file's own signature.
    with open(dest_path, "rb") as f:
        sig = f.read(4)
    if sig != b"PK\x03\x04":
        raise RuntimeError(f"{url}: response is not a real xlsx (got {sig!r} — likely a WAF/error page)")
    return size
