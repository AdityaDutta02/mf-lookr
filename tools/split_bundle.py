#!/usr/bin/env python3
"""Split a tools/out/<amc>_bundle.json into app/api/admin/seed-<amc>/data-N.json
chunk files small enough for GitHub's hard 100MB-per-file cap (well under it,
so a single fund's outsized disclosure row never pushes a chunk over). Each
chunk repeats the full amcs/funds identity rows (cheap — a handful of rows)
so lib/seed-data.ts's loadBundle() can merge+dedupe them back at request
time; only `disclosures` is actually partitioned across chunks.

Usage: python3 tools/split_bundle.py <amc_slug> [max_chunk_mb]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    if len(sys.argv) < 2:
        print("usage: split_bundle.py <amc_slug> [max_chunk_mb]", file=sys.stderr)
        return 1
    slug = sys.argv[1]
    max_chunk_bytes = int(float(sys.argv[2]) * 1_000_000) if len(sys.argv) > 2 else 40_000_000

    bundle_path = ROOT / "tools" / "out" / f"{slug}_bundle.json"
    bundle = json.loads(bundle_path.read_text())
    amcs, funds, disclosures = bundle["amcs"], bundle["funds"], bundle["disclosures"]

    out_dir = ROOT / "app" / "api" / "admin" / f"seed-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear any stale chunk/single files from a previous run so we never ship
    # a mix of old+new data.
    for stale in out_dir.glob("data*.json"):
        stale.unlink()

    header_overhead = len(json.dumps({"amcs": amcs, "funds": funds, "disclosures": []}))
    chunks = []
    current, current_bytes = [], header_overhead
    for row in disclosures:
        row_bytes = len(json.dumps(row))
        if current and current_bytes + row_bytes > max_chunk_bytes:
            chunks.append(current)
            current, current_bytes = [], header_overhead
        current.append(row)
        current_bytes += row_bytes
    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        # Small enough to stay a single data.json — matches the original
        # (unsplit) shape lib/seed-data.ts also understands.
        (out_dir / "data.json").write_text(json.dumps(bundle))
        print(f"{slug}: {len(disclosures)} disclosures fit in one data.json ({header_overhead/1e6:.1f}MB+)")
        return 0

    for i, chunk in enumerate(chunks):
        part = {"amcs": amcs, "funds": funds, "disclosures": chunk}
        path = out_dir / f"data-{i}.json"
        path.write_text(json.dumps(part))
        print(f"{slug}: chunk {i} -> {len(chunk)} disclosures, {path.stat().st_size/1e6:.1f}MB")

    print(f"{slug}: {len(disclosures)} disclosures across {len(chunks)} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
