# MF Lookr — local extraction toolkit

Not deployed. Runs locally to crawl each fund house's full detailed monthly factsheet
archive, parse holdings deterministically, and bulk-upload the result into the live
MF Lookr app. See project memory `project_mf_lookr_rebuild.md` decisions #9–12 and
the plan at `/Users/aditya/.claude/plans/abstract-munching-pudding.md`.

## Per-AMC pipeline

1. `discover_<amc>.py` — list every `(period, pdf_url)` in the archive.
2. `download_<amc>.py` — fetch PDFs to `cache/<amc>/`, keep them (uploaded to app storage later).
3. `parse_<amc>.py` — deterministic table parse → `out/<amc>/<period>/<fund>.json` (matches
   `lib/types.ts` `AnalyseData`, minus `amfi_code`/canonical name — filled in by identity resolution).
4. `resolve_identity.py` (shared) — match scheme names to AMFI's NAV master → canonical
   `amfi_code`/`scheme_name`/ISIN; also captures the daily NAV series.
5. `verify_<amc>.py` — assert `total_weight ∈ [99,101]`, `holdings_count>0`, spot-check.
6. `upload.ts` (shared, Node — reuses `../lib/db.ts`/`../lib/storage.ts`) — bulk-insert into
   the live app.

## Setup

```
cd tools
python3 -m venv .venv && source .venv/bin/activate
pip install pdfplumber openpyxl
```

Numbers policy: holdings weights/ISINs/market values are read from the PDF's literal table
cells via code. AI may assist building/debugging a parser, never in committed values.
