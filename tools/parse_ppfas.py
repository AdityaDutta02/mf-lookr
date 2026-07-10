#!/usr/bin/env python3
"""Deterministic PPFAS factsheet parser.

Uses docling (github.com/docling-project/docling) for layout-aware PDF ->
structured document conversion — it correctly separates PPFAS's two-column
page layout into properly ordered tables, which plain pdfplumber garbles.
All NUMBERS come from docling's table cells (literal PDF text), never from
an LLM — docling is a layout/OCR model, not a numbers-generating one.

Known fact about this source: PPFAS's factsheet PDF discloses NO ISIN for
any holding (equity or debt) — confirmed by grep over the full extracted
text. So downstream diffing must key on normalized security name for this
AMC (see lib/types.ts Holding.isin — left "" here).

Structure exploited (confirmed via doc.iterate_items() reading order):
  SectionHeaderItem(fund name) -> TableItem(key/value fund info, 2 cols)
    -> ... -> SectionHeaderItem("Portfolio Disclosure")
    -> one or more TableItem(holdings) immediately following
    -> ends at the next non-empty SectionHeaderItem.
Holdings tables have no reliable header row in some cases (debt tables
start straight into data); detect data rows by "last cell matches a %
pattern" instead of relying on headers. Section-label rows (only col0
filled, e.g. "Certificate of Deposit", "Commercial Paper", "Sub Total")
tag the instrument type for the data rows beneath them.
"""
import json
import re
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "cache" / "ppfas" / "pdf"
OUT_DIR = ROOT / "out" / "ppfas"

PCT_RE = re.compile(r"^[\s$]*-?\d+(\.\d+)?%\s*$")
# A wrapped sector/industry name can spill its tail word(s) into the weight cell
# (e.g. "Supplies 3.39%" where "Supplies" is the end of "Commercial Services &
# Supplies"). Match the trailing number+% instead of requiring the whole cell to
# be just a percentage, and recover the leftover text into the sector column.
TRAILING_PCT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%\s*$")
# Some dense debt-instrument sections (many short bond lines in a small font, seen in the
# Conservative Hybrid / Dynamic Asset Allocation Funds) get multiple physical rows merged into
# one docling grid row — the name/rating/weight cells each end up holding several securities'
# worth of text space-joined. ALL_PCT_RE finds every weight token in such a cell; NAME_SPLIT_RE
# finds the boundary between two bond names by their leading coupon rate (e.g. "...NCD (MD
# 11/06/2029) 7.64% National Bank..." splits before "7.64%").
ALL_PCT_RE = re.compile(r"-?\d+(?:\.\d+)?%")
NAME_SPLIT_RE = re.compile(r"(?=\d+(?:\.\d+)?\s?%\s*[A-Z])")
NUM_RE = re.compile(r"[^0-9.\-]")
DATE_SUFFIX_RE = re.compile(r"\s*\((?:MD\s*)?\d{2}/\d{2}/\d{4}\)\s*$")
SKIP_LABEL_RE = re.compile(r"^(sub\s*total|grand\s*total|total|net assets)\b", re.IGNORECASE)

SECTION_TYPE_MAP = [
    (re.compile(r"certificate of deposit", re.I), "cd"),
    (re.compile(r"commercial paper", re.I), "cp"),
    (re.compile(r"t-?bill|treasury bill", re.I), "tbill"),
    (re.compile(r"government (bond|security|securities)|g-?sec|state government", re.I), "gsec"),
    (re.compile(r"treps|reverse repo|repo", re.I), "treps"),
    (re.compile(r"mutual fund", re.I), "fund"),
    (re.compile(r"corporate (debt|bond)|debenture|\bncd\b|non.convertible", re.I), "corporate_debt"),
    (re.compile(r"cash|net (current|receivable)", re.I), "cash"),
    (re.compile(r"reit|invit", re.I), "reit"),
    (re.compile(r"future|option|derivative", re.I), "derivative"),
]

# Canonical current scheme name -> historical aliases. Schemes get renamed over a 13-year
# archive (e.g. Flexi Cap Fund was "PPFAS Long Term Value Fund" at 2013 launch, then "Parag
# Parikh Long Term Equity Fund" for years, before its current name) — matched against whichever
# name a given month's factsheet actually prints, but always stored under the CANONICAL name so
# a fund's history is one continuous series regardless of what it was called that month.
FUND_NAME_ALIASES = {
    "Parag Parikh Flexi Cap Fund": [
        "Parag Parikh Flexi Cap Fund",
        "Parag Parikh Long Term Equity Fund",
        "PPFAS Long Term Value Fund",
    ],
    "Parag Parikh ELSS Tax Saver Fund": ["Parag Parikh ELSS Tax Saver Fund", "Parag Parikh Tax Saver Fund"],
    "Parag Parikh Large Cap Fund": ["Parag Parikh Large Cap Fund"],
    "Parag Parikh Dynamic Asset Allocation Fund": ["Parag Parikh Dynamic Asset Allocation Fund"],
    "Parag Parikh Conservative Hybrid Fund": ["Parag Parikh Conservative Hybrid Fund"],
    "Parag Parikh Arbitrage Fund": ["Parag Parikh Arbitrage Fund"],
    "Parag Parikh Liquid Fund": ["Parag Parikh Liquid Fund"],
}
# Flat (alias, canonical) pairs, longest alias first so e.g. "...Long Term Equity Fund" doesn't
# shadow a longer, more specific match.
FUND_NAME_HINTS = sorted(
    ((alias, canonical) for canonical, aliases in FUND_NAME_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)


def num(v):
    if v is None:
        return None
    s = NUM_RE.sub("", str(v))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def classify_instrument(section_label, has_industry_col):
    # Try the section label against the known instrument-type patterns FIRST — a table can
    # have has_industry_col=True (equity's own header) yet later contain a REIT/T-Bill/TREPS
    # sub-section further down the same table (PPFAS packs multiple instrument blocks into
    # one "Portfolio Disclosure" table), so blindly trusting the header would mislabel those.
    if section_label:
        for pat, kind in SECTION_TYPE_MAP:
            if pat.search(section_label):
                return kind
    if has_industry_col:
        return "equity"
    return "debt"


def parse_holdings_table(grid):
    """grid: list[list[str]] raw table rows. Returns list of holding dicts."""
    if not grid:
        return []
    header = [c.strip() for c in grid[0]]
    has_industry_col = any(re.search(r"industry", h, re.I) for h in header)
    # If row 0 itself looks like a data row (last cell is a %), there's no header at all.
    header_is_data = bool(grid[0]) and PCT_RE.match(grid[0][-1] or "")
    rows = grid if header_is_data else grid[1:]

    holdings = []
    section_label = None
    pending = None  # (name, mid) of a name-bearing row whose weight hasn't shown up yet
    orphan_weight = None  # (weight, wrapped_tail) of a weight-only row whose name hasn't shown up yet
    suppress_orphan = False  # True right after a "Total"/"Sub total" marker row (no weight of its own)

    def emit(name_, mid_, weight_, wrapped_tail_):
        clean_name = DATE_SUFFIX_RE.sub("", name_).strip()
        instrument_type = classify_instrument(section_label, has_industry_col)
        sector_or_rating = " ".join(x for x in (mid_, wrapped_tail_) if x).strip() or (section_label or "")
        holdings.append({
            "name": clean_name, "isin": "", "industry": sector_or_rating,
            "weight": weight_, "type": instrument_type,
        })

    for row in rows:
        cells = [(c or "").strip() for c in row]
        while len(cells) < 3:
            cells.append("")
        # Some tables render a merged Name+Industry cell as two IDENTICAL grid columns
        # (a docling colspan artifact, seen in the Dynamic Asset Allocation Fund's holdings
        # table) — collapse the duplicate before treating cells[1] as a real "mid" column.
        if len(cells) >= 4 and cells[0] == cells[1]:
            cells = [cells[0]] + cells[2:]
        name, mid, last = cells[0], cells[1], cells[-1]
        pct_match = TRAILING_PCT_RE.search(last) if last else None

        if not name:
            if pct_match and not suppress_orphan:
                all_weights = ALL_PCT_RE.findall(last)
                if len(all_weights) > 1:
                    # Same dense-section merge as the named-row case, but the name-less row
                    # has no per-security names to split — keep the weight sum accurate by
                    # emitting one entry per weight token, sharing whatever name we have.
                    shared_name = pending[0] if pending else (section_label or "Unlabeled")
                    shared_mid = pending[1] if pending else ""
                    for tok in all_weights:
                        w = num(tok)
                        if w is not None:
                            emit(shared_name, shared_mid, w, "")
                else:
                    weight = num(pct_match.group(1))
                    wrapped_tail = last[: pct_match.start()].strip()
                    if weight is not None:
                        if pending:
                            # Normal case: a name-bearing row's weight overflowed onto the NEXT
                            # (empty-name) grid row — reattach it.
                            emit(pending[0], pending[1], weight, wrapped_tail)
                        else:
                            # Reverse case: the weight-only row came BEFORE its name row (seen in
                            # the Dynamic Asset Allocation Fund's TREPS row) — hold it and attach
                            # to whichever name-bearing row follows.
                            orphan_weight = (weight, wrapped_tail)
            pending = None
            # Suppression only applies to the single row immediately after a "Total" marker.
            suppress_orphan = False
            continue

        if not pct_match:
            is_skip = SKIP_LABEL_RE.match(name)
            # Name-bearing row with no weight of its own.
            if orphan_weight is not None and not is_skip:
                emit(name, mid, orphan_weight[0], orphan_weight[1])
                orphan_weight = None
                pending = None
                suppress_orphan = False
                continue
            # Otherwise: a section-label row — updates context, not a holding. A wrapped
            # section header can spill its tail into the "mid" column (e.g. "Reverse Repo /
            # TREPS and Other" | "Receivables and Payables" split across cols) so the label
            # text is name+mid combined, not just name. Also remember it as `pending` in case
            # its weight is on the NEXT (empty-name) grid row instead.
            label_text = f"{name} {mid}".strip()
            if label_text and not is_skip:
                section_label = label_text
            pending = None if is_skip else (name, mid)
            orphan_weight = None
            # A bare "Total"/"Sub total" marker row (no weight here) is very often followed by
            # its OWN aggregate weight on the next empty-name row (as in the Arbitrage Fund's
            # equity section: "Total" | "" | "" then "" | "" | "67.10%") — that next row is a
            # restated section total, not a new holding, so suppress orphan-capture for it.
            suppress_orphan = bool(is_skip)
            continue

        pending = None
        orphan_weight = None
        suppress_orphan = False
        if SKIP_LABEL_RE.match(name):
            continue  # "Sub Total" / "Net Assets" etc even if it slipped through with a % in last col

        all_weights = ALL_PCT_RE.findall(last)
        if len(all_weights) > 1:
            # Multiple securities' rows got merged into this one grid row (dense debt-instrument
            # section artifact). Split by weight count — every weight token is authoritative and
            # must be kept so total_weight stays accurate — and best-effort split/pad the name
            # and rating text to match. A handful of bond names at merge boundaries may end up
            # imprecisely attributed; the weight sum does not lose any value either way.
            name_frags = [f.strip() for f in NAME_SPLIT_RE.split(name) if f.strip() and f.strip()[0].isdigit()]
            rating_frags = mid.split() if mid else []
            n = len(all_weights)
            for i in range(n):
                w = num(all_weights[i])
                if w is None:
                    continue
                nm = name_frags[i] if i < len(name_frags) else (name_frags[-1] if name_frags else name)
                rt = rating_frags[i] if i < len(rating_frags) else (rating_frags[-1] if rating_frags else "")
                emit(nm, rt, w, "")
            continue

        weight = num(pct_match.group(1))
        if weight is None:
            continue
        # Text before the trailing number in `last` is a wrapped continuation of the sector/
        # industry column (e.g. "Supplies" in "...Commercial Services &" | "Supplies 3.39%").
        wrapped_tail = last[: pct_match.start()].strip()
        emit(name, mid, weight, wrapped_tail)
    return holdings


NON_HOLDINGS_HEADER_RE = re.compile(
    r"scheme|units|aum\s*\(|performance|rolling return|dividend|record date|"
    r"since inception|load structure|quantit|name of the fund|entry load|"
    r"potential risk|fund manager",
    re.IGNORECASE,
)


def looks_like_holdings_table(grid):
    if not grid or len(grid) < 2:
        return False
    ncols = max(len(r) for r in grid)
    if ncols not in (3, 4):
        return False
    header_text = " ".join((c or "") for c in grid[0])
    if NON_HOLDINGS_HEADER_RE.search(header_text):
        return False
    pct_rows = sum(1 for r in grid if r and TRAILING_PCT_RE.search((r[-1] or "").strip()))
    return pct_rows >= 3


def parse_fund_info(grid):
    """grid from the 'Name of the Fund' key/value table -> dict of raw fields."""
    info = {}
    for row in grid:
        if len(row) < 2:
            continue
        key = (row[0] or "").strip()
        val = (row[1] or "").strip()
        if key:
            info[key] = val
    return info


def parse_pdf(pdf_path: Path, period: str):
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    funds = {}  # fund_name -> {"info": {...}, "holdings": [...]}
    current_fund = None
    seen_info_for = set()

    for item, _level in doc.iterate_items():
        cls = type(item).__name__
        if cls == "SectionHeaderItem":
            text = (getattr(item, "text", "") or "").strip()
            match = next(
                (canonical for alias, canonical in FUND_NAME_HINTS if text == alias or text in alias or alias in text),
                None,
            )
            if match:
                current_fund = match
            continue
        if cls != "TableItem" or current_fund is None:
            continue

        grid_rows = [[c.text for c in row] for row in item.data.grid]
        if not grid_rows:
            continue

        bucket = funds.setdefault(current_fund, {"info": {}, "holdings": [], "pages": set()})

        # Key/value fund-info table: 2 cols, first row is "Name of the Fund" -> value.
        if (
            current_fund not in seen_info_for
            and len(grid_rows[0]) == 2
            and (grid_rows[0][0] or "").strip().lower().startswith("name of the fund")
        ):
            bucket["info"] = parse_fund_info(grid_rows)
            seen_info_for.add(current_fund)
            continue

        if looks_like_holdings_table(grid_rows):
            bucket["holdings"].extend(parse_holdings_table(grid_rows))
            if item.prov:
                bucket["pages"].add(item.prov[0].page_no)

    return funds


# A fund's holdings table is "trustworthy" only within this band — PPFAS's own printed
# subtotals carry ~1-2pp of rounding drift from their per-line-item rounding, so this is
# intentionally looser than a strict [99,101]; anything further off signals a real
# extraction problem (row-fusion across a dense debt table), not just rounding.
TRUST_BAND = (97.0, 103.0)


def rescue_via_page_image(pdf_path: Path, page_nos, dpi: int = 400):
    """Re-render specific pages as high-DPI images and reparse through docling's image
    pipeline. Bypasses the native PDF text-layer table reconstruction entirely — useful when
    that path scrambles a dense, small-font table (bond names/weights split across grid rows
    in inconsistent order) that the image+OCR path reconstructs far more reliably in practice.
    """
    import pdfplumber

    holdings = []
    converter = DocumentConverter()
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no in sorted(page_nos):
            page = pdf.pages[page_no - 1]
            img_path = ROOT / "cache" / f"_rescue_p{page_no}.png"
            page.to_image(resolution=dpi).save(str(img_path))
            result = converter.convert(str(img_path))
            img_path.unlink(missing_ok=True)
            for t in result.document.tables:
                grid_rows = [[c.text for c in row] for row in t.data.grid]
                if looks_like_holdings_table(grid_rows):
                    holdings.extend(parse_holdings_table(grid_rows))
    return holdings


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else "2026-05"
    pdf_path = PDF_DIR / f"{period}.pdf"
    if not pdf_path.exists():
        print(f"no PDF for {period} at {pdf_path}")
        return 1

    funds = parse_pdf(pdf_path, period)

    print(f"Parsed {len(funds)} funds for {period}:")
    for name, bucket in funds.items():
        total = sum(h["weight"] for h in bucket["holdings"])
        if not (TRUST_BAND[0] <= total <= TRUST_BAND[1]) and bucket["pages"]:
            print(f"  {name}: text-layer total_weight={total:.2f}% outside trust band — rescuing via page image...")
            rescued = rescue_via_page_image(pdf_path, bucket["pages"])
            rescued_total = sum(h["weight"] for h in rescued)
            if TRUST_BAND[0] <= rescued_total <= TRUST_BAND[1]:
                bucket["holdings"] = rescued
                total = rescued_total
                bucket["rescued"] = True
            else:
                print(f"    rescue attempt total={rescued_total:.2f}% — still outside band, keeping text-layer result")
        bucket.pop("pages", None)
        flag = " [RESCUED]" if bucket.get("rescued") else ""
        print(f"  {name}: {len(bucket['holdings'])} holdings, total_weight={total:.2f}%{flag}, "
              f"aum={bucket['info'].get('Assets Under Management (AUM) as on May 31, 2026', bucket['info'].get('Name of the Fund'))}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{period}.json"
    out_path.write_text(json.dumps(funds, indent=2))
    print(f"Written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
