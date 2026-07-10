"""Shared HTTP helpers — shell out to curl instead of urllib to sidestep the
macOS python.org framework build's broken local cert store (SSL_CERT_FILE
issue with urllib/ssl). curl uses the system trust store correctly."""
import subprocess

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def fetch_text(url: str) -> str:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "--fail", url],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout.decode("utf-8", errors="replace")


def download_file(url: str, dest_path: str) -> int:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "--fail", "-o", dest_path, url],
        capture_output=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr.decode(errors='replace')[:300]}")
    import os
    return os.path.getsize(dest_path)
