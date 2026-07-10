# MF Lookr

Built on [Terminal AI](https://terminalai.studioionique.com). See `/Users/aditya/.claude/plans/abstract-munching-pudding.md` for the full rebuild plan and project memory `project_mf_lookr_rebuild.md` for locked decisions.

## Two separate parts

- **This app** (`app/`, `lib/`, `components/`) — thin storage + display layer. Reads `amcs`/`funds`/`disclosures`/`navs` from Postgres (see `db-migrations.sql`), computes month-over-month changes server-side, and generates the AI narrative from those changes. Does **not** parse factsheets.
- **`tools/`** — local extraction toolkit (not deployed). Crawls each fund house's factsheet archive, parses PDFs deterministically into the `AnalyseData` contract (`lib/types.ts`), and bulk-uploads the result into this app via the gateway. See `tools/README.md`.

## Schema

`amcs → funds → disclosures (year/month) / navs`, all relational — no per-AMC tables. A new fund house is new rows, not a migration. Full rationale in `db-migrations.sql` comments.

## Build order

PPFAS → HDFC → Axis → Invesco → SBI → Nippon India → Navi → Motilal Oswal → Mirae Asset → ICICI → Helios, one at a time, each tested via `app_preview` before the next. Source links in the mf-analyser repo's `FUND_HOUSE_LINKS.md`.
