#!/usr/bin/env python3
"""Join parsed Motilal Oswal periods (tools/out/motilal_xlsx/<period>.json — from
the "Scheme Portfolio Details" / "Month End Portfolio" XLS/XLSX, NOT the
factsheet PDF; see parse_motilal_xlsx.py) with AMFI identity into the app's
AnalyseData contract, and emit tools/out/motilal_bundle.json in the
{amcs, funds, disclosures} shape the seed route inserts directly. Mirrors
tools/build_dataset.py (PPFAS).

Deterministic derivation only — no AI, no guessed numbers. Each holding's own
ISIN/quantity/market value comes straight from the source XLS.

IDENTITY MATCHING. Unlike PPFAS (7 funds, hand-mapped), Motilal has 85+ live
schemes and 13+ years of scheme-name history (renames, spacing/punctuation
drift, typos — see the ~136 distinct name spellings collected across the
archive). Hand-mapping every spelling isn't practical, so identity is resolved
by normalized-token matching against tools/cache/amfi_nav.txt:

  - candidate AMFI rows are restricted to scheme names containing "motilal"
  - non-ETF schemes are further restricted to the Direct + Growth plan variant
    (ETFs have no plan variants in the AMFI file at all — single NAV)
  - both the canonical XLS fund name and each AMFI candidate name are reduced
    to a token set (AMC boilerplate / plan words stripped, everything else
    kept — "nifty", "bse", "index", "50" etc all matter for disambiguation)
  - the AMFI candidate with the highest Jaccard token overlap wins, provided
    that overlap clears MATCH_THRESHOLD

Anything that doesn't clear the threshold is logged to stderr and dropped —
never guessed. This is expected to affect only defunct/heavily-renamed old
scheme names (e.g. "Motilal Oswal MOSt Focused Midcap30 Fund" from 2016);
current scheme names all match cleanly.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "motilal_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
DAYS_IN_MONTH = ["31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"]

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill"}
EQUITY_TYPES = {"equity", "reit"}

MATCH_THRESHOLD = 0.5

# Direct evidence from the source workbook's own "Index" sheet, which annotates
# several current schemes with "(Formerly known as ...)" / "(Previously known
# as ...)" — this is on-site evidence, not a guess. A couple of additional
# very-common old spellings/typos observed across the archive are folded in
# too. Anything genuinely retired (no live successor identifiable this way)
# is left to fall through to the unmatched-and-logged path.
NAME_ALIASES = {
    "Motilal Oswal Dynamic Fund": "Motilal Oswal Balanced Advantage Fund",
    "Motilal Oswal Balance Advantage Fund": "Motilal Oswal Balanced Advantage Fund",  # typo
    "Motilal Oswal Long Term Equity Fund": "Motilal Oswal ELSS Tax Saver Fund",
    "Motilal Oswal MOSt Focused Long Term Fund": "Motilal Oswal ELSS Tax Saver Fund",
    "Motilal Oswal MOSt Focused Long Term Fn": "Motilal Oswal ELSS Tax Saver Fund",  # truncated header
    "Motilal Oswal M50 ETF": "Motilal Oswal Nifty 50 ETF",
    "Motilal Oswal MOSt Shares M50 ETF": "Motilal Oswal Nifty 50 ETF",
    "Motilal Oswal Flexicap Fund": "Motilal Oswal Flexi Cap Fund",
    "Motilal Oswal500 Index Fund": "Motilal Oswal Nifty 500 Index Fund",  # source typo, missing "Nifty "
}

STOP_TOKENS = {
    "motilal", "oswal", "mo", "fund", "funds", "the", "of", "plan", "direct",
    "regular", "growth", "option", "previously", "known", "as", "formerly",
    "scheme", "s", "most", "shares",
}
PUNCT_RE = re.compile(r"[^a-z0-9]+")


def tokenize(name: str) -> set:
    norm = PUNCT_RE.sub(" ", name.lower()).split()
    return {t for t in norm if t and t not in STOP_TOKENS}


def load_amfi_candidates():
    """Returns list of (tokens, code, isin, scheme_name) for every Motilal Oswal
    AMFI row, restricted to Direct+Growth for plan-based schemes (ETFs have no
    plan variant in AMFI's file, so those are kept as-is)."""
    candidates = []
    for line in AMFI_PATH.read_text(errors="replace").splitlines():
        parts = line.split(";")
        if len(parts) < 4:
            continue
        code, isin_growth, _isin_reinvest, scheme_name = parts[0], parts[1], parts[2], parts[3]
        if not code.strip().isdigit():
            continue
        lname = scheme_name.lower()
        if "motilal" not in lname:
            continue
        is_etf = "etf" in lname
        if not is_etf:
            # Growth is usually implied/default rather than spelled out (e.g.
            # "Motilal Oswal BSE Quality Index Fund-Direct plan" has no "growth"
            # token at all) — requiring "direct" present and "regular" absent is
            # enough; still hard-exclude non-growth income options by name.
            if "direct" not in lname or "regular" in lname:
                continue
            if any(k in lname for k in ("idcw", "dividend", "bonus", "reinvest")):
                continue
        if isin_growth in ("-", "", None):
            continue
        candidates.append((tokenize(scheme_name), code.strip(), isin_growth.strip(), scheme_name.strip()))
    return candidates


def best_match(canonical_name: str, candidates):
    target = tokenize(canonical_name)
    if not target:
        return None
    best, best_score = None, 0.0
    for tokens, code, isin, scheme_name in candidates:
        if not tokens:
            continue
        inter = len(target & tokens)
        union = len(target | tokens)
        score = inter / union if union else 0.0
        if score > best_score:
            best_score, best = score, (code, isin, scheme_name)
    if best_score >= MATCH_THRESHOLD:
        return best
    return None


def category_for(name: str) -> str:
    n = name.lower()
    is_etf = "etf" in n
    is_index = "index" in n
    rules = [
        (r"liquid", "Debt - Liquid Fund"),
        (r"ultra short", "Debt - Ultra Short Duration Fund"),
        (r"\barbitrage\b", "Hybrid - Arbitrage Fund"),
        (r"balanc(ed|e) advantage|dynamic fund", "Hybrid - Dynamic Asset Allocation"),
        (r"multi asset", "Hybrid - Multi Asset Allocation"),
        (r"elss|tax saver|long term equity", "Equity - ELSS"),
        (r"large\s*(and|&)\s*mid\s*cap", "Equity - Large & Mid Cap Fund"),
        (r"large\s*cap", "Equity - Large Cap Fund"),
        (r"multi\s*cap", "Equity - Multi Cap Fund"),
        (r"flexi\s*cap", "Equity - Flexi Cap Fund"),
        (r"small\s*cap", "Equity - Small Cap Fund"),
        (r"mid\s*cap", "Equity - Mid Cap Fund"),
        (r"microcap", "Equity - Small Cap Fund"),
        (r"quant fund", "Equity - Quant Fund"),
        (r"contra", "Equity - Contra Fund"),
        (r"focused", "Equity - Focused Fund"),
        (r"gold.*silver|silver.*gold", "Other - FoF (Gold + Silver)"),
        (r"\bgold\b", "Other - Gold ETF" if is_etf else "Other - FoF (Gold)"),
        (r"\bsilver\b", "Other - Silver ETF" if is_etf else "Other - FoF (Silver)"),
        (r"g-?sec|gilt", "Other - Debt ETF" if is_etf else "Other - FoF (Debt)"),
        (r"fund of fund|\bfof\b", "Other - Fund of Funds"),
        (r"manufacturing|digital india|consumption|financial services|"
         r"\bservices fund\b|innovation opportunities|business cycle|"
         r"special opportunities|infrastructure", "Equity - Sectoral/Thematic Fund"),
        (r"momentum", "Other - Index Fund" if is_index else "Other - ETF"),
    ]
    for pat, cat in rules:
        if re.search(pat, n):
            return cat
    if is_etf:
        return "Other - ETF"
    if is_index:
        return "Other - Index Fund"
    return "Equity - Sectoral/Thematic Fund"


def asset_class_for(holdings):
    total = sum(h["weight"] for h in holdings) or 1
    eq_pct = sum(h["weight"] for h in holdings if h["type"] in EQUITY_TYPES) / total * 100
    if eq_pct > 65:
        return "equity"
    if eq_pct < 25:
        return "debt"
    return "hybrid"


def asset_allocation(holdings):
    buckets = {"Equity": 0.0, "Debt": 0.0, "Others": 0.0}
    for h in holdings:
        if h["type"] in EQUITY_TYPES:
            buckets["Equity"] += h["weight"]
        elif h["type"] in ("fund", "derivative"):
            buckets["Others"] += h["weight"]
        else:
            buckets["Debt"] += h["weight"]
    return [{"name": k, "weight": round(v, 2)} for k, v in buckets.items() if v > 0.001]


def category_breakdown(holdings, top_n=8):
    agg = {}
    for h in holdings:
        raw = h.get("industry")
        key = (str(raw).strip() if raw else "") or "Unclassified"
        agg[key] = agg.get(key, 0.0) + h["weight"]
    rows = sorted(({"name": k, "weight": round(v, 2)} for k, v in agg.items()), key=lambda r: -r["weight"])
    return rows[:top_n]


def build_disclosure(canonical_name, code, isin, scheme_name, category, period, bucket):
    holdings = bucket["holdings"]
    total_weight = round(sum(h["weight"] for h in holdings), 2)
    top_holdings = sorted(holdings, key=lambda h: -h["weight"])[:10]
    deployable_cash = round(sum(h["weight"] for h in holdings if h["type"] in DEPLOYABLE_TYPES), 2)
    aum = round(sum(h["market_value_cr"] for h in holdings if h.get("market_value_cr") is not None), 2)
    year, month = period.split("-")
    data = {
        "amfi_code": code,
        "scheme_name": scheme_name,
        "amc_name": "Motilal Oswal Mutual Fund",
        "category": category,
        "isin": isin,
        "asset_class": asset_class_for(holdings),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{DAYS_IN_MONTH[int(month) - 1]}",
        "source_org": "Motilal Oswal Mutual Fund",
        "source_url": "https://www.motilaloswalmf.com/downloads/scheme-portfolio-details",
        "aum": aum or None,
        "nav": None,
        "expense_ratio": None,
        "holdings_count": len(holdings),
        "total_weight": total_weight,
        "deployable_cash": deployable_cash,
        "asset_allocation": asset_allocation(holdings),
        "category_breakdown": category_breakdown(holdings),
        "market_cap_breakdown": [],
        "cash_breakdown": [{"section": "Cash & Money Market", "weight": deployable_cash}] if deployable_cash else [],
        "top_holdings": [
            {"name": h["name"], "isin": h["isin"], "sector": str(h.get("industry") or ""), "weight": h["weight"]}
            for h in top_holdings
        ],
        "holdings": [
            {
                "name": h["name"], "isin": h["isin"], "instrument_type": h["type"],
                "sector": str(h.get("industry") or ""), "weight": h["weight"],
                "market_value": h.get("market_value_cr") or 0, "quantity": h.get("quantity") or 0,
            }
            for h in holdings
        ],
    }
    return {
        "amfi_code": code,
        "amc_slug": "motilal",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "Motilal Oswal Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }


def main():
    # Default to the last 18 parsed months — matches the window the other AMCs
    # loaded alongside this one (HDFC ~34MB, Nippon ~37MB shipped bundles) so
    # coverage across the app is roughly even. Motilal has 84+ live schemes vs
    # PPFAS's 7, many with hundreds of holdings each (BSE 1000 Index Fund
    # alone: 906), so dumping ALL 165 parsed months at once would produce a
    # ~90MB bundle — not attempted. Pass explicit period args (e.g. "2026-05
    # 2026-06") to load a different/additional window instead.
    all_periods = sorted(p.stem for p in OUT_DIR.glob("*.json"))
    periods = sys.argv[1:] or all_periods[-18:]
    amcs = [{
        "slug": "motilal", "name": "Motilal Oswal Mutual Fund",
        "factsheet_url": "https://www.motilaloswalmf.com/downloads/factsheets",
        "archive_from": "2012-10", "status": "loaded",
    }]
    funds = []
    disclosures = []
    seen_funds = set()

    candidates = load_amfi_candidates()
    identity_cache = {}  # canonical_name -> (code, isin, scheme_name, category) or None
    unmatched = set()
    matched_count = 0

    for period in periods:
        path = OUT_DIR / f"{period}.json"
        if not path.exists():
            print(f"skip {period}: not parsed yet")
            continue
        parsed = json.loads(path.read_text())
        for canonical_name, bucket in parsed.items():
            if canonical_name not in identity_cache:
                lookup_name = NAME_ALIASES.get(canonical_name, canonical_name)
                m = best_match(lookup_name, candidates)
                if m is None:
                    identity_cache[canonical_name] = None
                else:
                    code, isin, scheme_name = m
                    identity_cache[canonical_name] = (code, isin, scheme_name, category_for(lookup_name))
            ident = identity_cache[canonical_name]
            if ident is None:
                unmatched.add(canonical_name)
                continue
            code, isin, scheme_name, category = ident
            matched_count += 1
            if code not in seen_funds:
                funds.append({
                    "amc_slug": "motilal",
                    "amfi_code": code,
                    "scheme_name": scheme_name,
                    "isin_growth": isin,
                    "isin_reinvest": None,
                    "category": category,
                    "asset_class": asset_class_for(bucket["holdings"]),
                    "plan_type": "direct-growth" if "direct" in scheme_name.lower() else "single",
                })
                seen_funds.add(code)
            disclosures.append(build_disclosure(canonical_name, code, isin, scheme_name, category, period, bucket))

    bundle = {"amcs": amcs, "funds": funds, "disclosures": disclosures}
    out_path = ROOT / "out" / "motilal_bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2))
    print(f"{len(funds)} funds, {len(disclosures)} disclosures ({matched_count} fund-months matched) -> {out_path}")
    if unmatched:
        print(f"\n{len(unmatched)} distinct fund-name spellings never matched an AMFI identity (dropped, not guessed):", file=sys.stderr)
        for n in sorted(unmatched):
            print(f"  - {n!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
