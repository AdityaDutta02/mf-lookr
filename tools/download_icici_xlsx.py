#!/usr/bin/env python3
"""Download every entry in the ICICI portfolio-disclosure manifest to
cache/icici/xlsx/<period>/<scheme-slug>.xlsx. Most months are a single ZIP
covering every scheme (~140+ schemes/month in recent months) — unzipped in
place, one .xlsx per scheme, same directory shape as HDFC's
cache/hdfc/xlsx/<period>/<scheme>.xlsx even though the source layout differs
(HDFC: many individual URLs; ICICI: one ZIP URL, expanded locally). Loose
non-zip entries (a handful of ad-hoc/interim files, mostly pre-2021) are
downloaded as-is under a slug derived from their title.

--limit N caps how many NEW period-entries this run downloads (existing
periods already fully unpacked on disk don't count against it) — same
resume/chunking contract as download_hdfc_xlsx.py, since 161 months x ~140
files/month is a lot of data to pull in one shot.

--since YYYY-MM restricts to periods >= that value (the task's stated bar is
"last 12-18 months" as the minimum useful target; full history is nice-to-have
and can be pulled in a later run by omitting --since).
"""
import json
import re
import sys
import zipfile
from pathlib import Path

from http_util_icici import download_file

ROOT = Path(__file__).parent
MANIFEST = ROOT / "cache" / "icici" / "xlsx_manifest.json"
XLSX_DIR = ROOT / "cache" / "icici" / "xlsx"
RAW_DIR = ROOT / "cache" / "icici" / "raw"  # downloaded zips/loose files, kept for re-runs

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-")


def unpack_zip(zip_path: Path, period_dir: Path) -> int:
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            ext = Path(name).suffix.lower()
            if ext not in (".xlsx", ".xls"):
                continue
            dest = period_dir / f"{slug(Path(name).stem)}{ext}"
            with z.open(info) as src, open(dest, "wb") as out:
                out.write(src.read())
            n += 1
    return n


def main():
    limit = None
    since = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--since="):
            since = arg.split("=", 1)[1]

    entries = json.loads(MANIFEST.read_text())
    if since:
        entries = [e for e in entries if e["period"] >= since]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    XLSX_DIR.mkdir(parents=True, exist_ok=True)

    ok, skipped, failed = 0, 0, []
    processed_periods_this_run = set()

    for e in entries:
        period_dir = XLSX_DIR / e["period"]
        ext = Path(e["url"]).suffix.lower()
        raw_name = f"{e['period']}__{slug(e['title'])}{ext}"
        raw_path = RAW_DIR / raw_name

        already_unpacked = period_dir.exists() and any(period_dir.iterdir())
        if raw_path.exists() and raw_path.stat().st_size > 1_000 and (ext != ".zip" or already_unpacked):
            skipped += 1
            continue

        if limit is not None and len(processed_periods_this_run) >= limit and e["period"] not in processed_periods_this_run:
            print(f"\nHit --limit={limit} new periods, stopping (resume by re-running).")
            break

        try:
            download_file(e["url"], str(raw_path))
            period_dir.mkdir(parents=True, exist_ok=True)
            if ext == ".zip":
                n = unpack_zip(raw_path, period_dir)
                print(f"  {e['period']}  {e['title']}  -> {n} scheme files")
            else:
                dest = period_dir / f"{slug(e['title'])}{ext}"
                dest.write_bytes(raw_path.read_bytes())
                print(f"  {e['period']}  {e['title']}  (loose file)")
            processed_periods_this_run.add(e["period"])
            ok += 1
        except Exception as ex:
            print(f"  {e['period']}  {e['title']}  FAILED: {ex}")
            failed.append((e["period"], e["title"]))

    print(f"\nProcessed {ok}, already cached {skipped}, failed {len(failed)}")
    if failed:
        print("Failed:", failed[:30], "..." if len(failed) > 30 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
