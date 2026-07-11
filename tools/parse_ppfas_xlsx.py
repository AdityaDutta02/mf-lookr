#!/usr/bin/env python3
"""Deterministic parser for PPFAS's "Detailed Portfolio Disclosure" XLS —
the SEBI-mandated monthly portfolio statement, NOT the marketing factsheet
PDF (see tools/parse_ppfas.py, superseded for months this file covers).

Despite the .xls extension the file is real OOXML (openpyxl needs a .xlsx
copy to load it — see tools/README.md). One sheet per scheme, consistent
columns: Name of the Instrument | ISIN | Industry/Rating | Quantity |
Market/Fair Value (Rs. Lakhs) | % to Net Assets | YTM | YTC.

Row classification is simple and robust: a row with a non-empty ISIN is a
real holding (numbers straight from the cell — no LLM, no OCR). A row with
no ISIN is either a section-label ("Equity & Equity related", "Debt
Instruments", "(a) Listed / awaiting listing...") or a Sub Total/Total/
GRAND TOTAL marker — both skipped as holdings, the label ones update
classification context for rows beneath them. GRAND TOTAL's own weight
(always ~1.0) is a free per-sheet validation check.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl
import xlrd

ROOT = Path(__file__).parent
CACHE_DIR = ROOT / "cache" / "ppfas" / "xlsx"
OUT_DIR = ROOT / "out" / "ppfas_xlsx"

SKIP_RE = re.compile(r"^(sub\s*total|total|grand\s*total)\b", re.IGNORECASE)

SECTION_TYPE_MAP = [
    (re.compile(r"certificate of deposit", re.I), "cd"),
    (re.compile(r"commercial paper", re.I), "cp"),
    (re.compile(r"treasury\s*bill|t-?\s*bills?\b", re.I), "tbill"),
    # "Goverment" (sic) is a real recurring typo in PPFAS's own sheet — gov(?:ern|er)ment
    # matches both "government" and the typo'd "goverment".
    (re.compile(r"gov(?:ern|er)ment (bond|security|securities)|g-?sec|state (govern|gover)ment|state development loan", re.I), "gsec"),
    (re.compile(r"treps|reverse repo|repo", re.I), "treps"),
    (re.compile(r"mutual fund", re.I), "fund"),
    (
        re.compile(
            r"corporate (debt|bond)|debenture|\bncd\b|non.convertible|money market|"
            r"\bdebt instrument|\bdebt securit",
            re.I,
        ),
        "corporate_debt",
    ),
    (re.compile(r"cash|net (current|receivable)", re.I), "cash"),
    (re.compile(r"reit|invit", re.I), "reit"),
    (re.compile(r"future|option|derivative|hedg", re.I), "derivative"),
    (re.compile(r"equity", re.I), "equity"),
]


def classify(section_label: str, name: str = "") -> str:
    # section_label first — this format's section headers are clean and reliable
    # ("Equity & Equity related", "Certificate of Deposit", "Government Securities",
    # ...), so trust it over the row's own name (a company literally named e.g.
    # "Future Retail Limited" would otherwise false-positive-match the "future"
    # derivative pattern). Only fall back to the row's own name for holdings that
    # stand alone with no preceding label row of their own, like "Net Receivables /
    # (Payables)".
    for text in (section_label, name):
        for pat, kind in SECTION_TYPE_MAP:
            if pat.search(text or ""):
                return kind
    return "equity"  # default: most unlabeled-section rows in this format are equity


def num(v):
    if v is None or v == "" or v == "NIL":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


COLUMN_NAME_PATTERNS = {
    "name": re.compile(r"name of the instrument", re.I),
    "isin": re.compile(r"^isin", re.I),
    "industry": re.compile(r"industry|rating", re.I),
    "quantity": re.compile(r"quantity", re.I),
    "market_value": re.compile(r"market.*value", re.I),
    # Older sheets (pre ~2023) say "% to AUM" instead of "% to Net Assets".
    "weight": re.compile(r"%\s*to\s*(net|aum)", re.I),
}


def load_workbook_rows(path: Path):
    """Returns {sheet_name: [[cell, ...], ...]} regardless of whether the file
    is real OOXML (renamed .xlsx, openpyxl) or legacy BIFF8 (genuine .xls,
    xlrd) — PPFAS serves both under a ".xls" URL depending on how old the
    month is. Detect by the actual file signature, not the extension."""
    with open(path, "rb") as f:
        sig = f.read(4)
    if sig == b"PK\x03\x04":
        wb = openpyxl.load_workbook(str(path), data_only=True)
        return {name: [list(row) for row in wb[name].iter_rows(values_only=True)] for name in wb.sheetnames}
    wb = xlrd.open_workbook(str(path))
    return {name: [wb.sheet_by_name(name).row_values(i) for i in range(wb.sheet_by_name(name).nrows)]
            for name in wb.sheet_names()}


def find_fund_name(rows):
    """Fund name location varies by era (new format: row0 col1; old format:
    a 'SCHEME NAME :' labeled cell further down) — scan for it by content
    instead of a fixed position: the longest cell text containing "Fund"
    in the first few rows is reliably the scheme's full descriptive name."""
    best = None
    for r in rows[:8]:
        for c in r:
            if isinstance(c, str) and "fund" in c.lower() and len(c) > 10:
                if best is None or len(c) > len(best):
                    best = c
    if not best:
        return None
    return re.sub(r"\s*\(.*$", "", best).strip()


def locate_columns(header_row):
    cols = {}
    for i, cell in enumerate(header_row):
        if not isinstance(cell, str):
            continue
        for key, pat in COLUMN_NAME_PATTERNS.items():
            if key not in cols and pat.search(cell):
                cols[key] = i
    return cols


def parse_sheet(rows):
    """rows: list[list[cell]] — from either openpyxl or xlrd, via load_workbook_rows()."""
    header_idx = next((i for i, r in enumerate(rows) if r and any(
        isinstance(c, str) and COLUMN_NAME_PATTERNS["name"].search(c) for c in r
    )), None)
    if header_idx is None:
        return {"holdings": [], "grand_total": None, "fund_name": None}

    cols = locate_columns(rows[header_idx])
    if "name" not in cols or "weight" not in cols:
        return {"holdings": [], "grand_total": None, "fund_name": None}

    fund_name = find_fund_name(rows)
    if not fund_name:
        return {"holdings": [], "grand_total": None, "fund_name": None}

    holdings = []
    section_label = None
    grand_total = None

    def cell(r, key):
        idx = cols.get(key)
        return r[idx] if idx is not None and idx < len(r) else None

    for r in rows[header_idx + 1:]:
        if not r:
            continue
        raw_name = cell(r, "name")
        name = raw_name.strip() if isinstance(raw_name, str) else raw_name
        if not name:
            continue
        if isinstance(name, str) and SKIP_RE.match(name):
            if name.strip().upper() == "GRAND TOTAL":
                grand_total = num(cell(r, "weight"))
                # Everything after GRAND TOTAL is a DIFFERENT table (performance/
                # returns/dividend history) whose columns coincidentally hold numeric
                # junk in these same positions — stop here or it gets misread as holdings.
                break
            continue

        weight_frac = num(cell(r, "weight"))
        if weight_frac is None:
            # No weight in this row at all -> it's a section-label row (e.g. "Equity &
            # Equity related", "Certificate of Deposit"), not a holding. Some genuine
            # holdings (TREPS, Net Receivables/Payables) have NO isin, so isin presence
            # alone can't be the data-row signal — weight presence is what's reliable.
            #
            # Labels nest two levels deep ("Debt Instruments" -> "(a) Listed / awaiting
            # listing on Stock Exchange") and the sub-label is reused verbatim under BOTH
            # equity and debt top-level sections, so it carries no type information of its
            # own. Only overwrite the tracked label when the new text itself matches a
            # known category — otherwise a meaningless structural sub-header would wipe
            # out the correct top-level label the holdings beneath it actually belong to.
            if isinstance(name, str) and any(pat.search(name) for pat, _ in SECTION_TYPE_MAP):
                section_label = name
            continue

        isin = cell(r, "isin")
        industry = cell(r, "industry")
        industry = industry.strip() if isinstance(industry, str) else (industry or "")
        quantity = num(cell(r, "quantity"))
        market_value_lakhs = num(cell(r, "market_value"))
        holdings.append({
            "name": name.strip() if isinstance(name, str) else str(name),
            "isin": (isin.strip() if isinstance(isin, str) else "") or "",
            "industry": industry,
            "quantity": quantity,
            "market_value_cr": round(market_value_lakhs / 100, 4) if market_value_lakhs is not None else None,
            "weight": round(weight_frac * 100, 4),
            "type": classify(section_label, name if isinstance(name, str) else ""),
        })

    return {"holdings": holdings, "grand_total": grand_total, "fund_name": fund_name}


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else None
    xlsx_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if not xlsx_path:
        print("usage: parse_ppfas_xlsx.py <period YYYY-MM> <path to .xlsx>")
        return 1

    sheets = load_workbook_rows(xlsx_path)
    funds = {}
    for sheet_name, rows in sheets.items():
        parsed = parse_sheet(rows)
        if not parsed["fund_name"]:
            continue
        total = round(sum(h["weight"] for h in parsed["holdings"]), 2)
        gt = parsed["grand_total"]
        gt_pct = round(gt * 100, 2) if gt is not None else None
        ok = gt_pct is not None and abs(total - gt_pct) < 0.5
        print(f"  {parsed['fund_name']}: {len(parsed['holdings'])} holdings, "
              f"sum={total:.2f}%, GRAND TOTAL={gt_pct}%, {'OK' if ok else 'MISMATCH'}")
        funds[parsed["fund_name"]] = {"holdings": parsed["holdings"], "grand_total_pct": gt_pct}

    if period:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"{period}.json"
        out_path.write_text(json.dumps(funds, indent=2))
        print(f"Written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
