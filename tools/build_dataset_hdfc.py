#!/usr/bin/env python3
"""Join parsed HDFC periods (tools/out/hdfc_xlsx/<period>.json — from
parse_all_hdfc_xlsx.py) with AMFI identity into the app's AnalyseData
contract, and emit tools/out/hdfc_bundle.json in the same {amcs, funds,
disclosures} shape as ppfas_bundle.json (amc_slug: "hdfc" throughout).

Unlike build_dataset.py's small hardcoded AMFI_IDENTITY dict (7 PPFAS
schemes), HDFC has 100+ schemes — a name-matching pass against
cache/amfi_nav.txt instead. AMFI scheme names encode plan/option as
trailing " - <clause>" segments (e.g. "HDFC Flexi Cap Fund - Growth Option
- Direct Plan", "HDFC NIFTY 50 ETF - Growth Plan" for single-NAV
instruments with no plan split). Strategy: for every AMFI row under the
"HDFC Mutual Fund" section, strip known plan/option clauses to recover the
scheme's base name, keep the best-ranked variant per base name (Direct+
Growth > Growth-only > first seen), then match each parsed xlsx scheme name
to a base name by normalized exact match, falling back to a fuzzy
best-match (difflib) above a conservative cutoff. Anything that still
doesn't match is logged and DROPPED (never guessed) — see the "unmatched"
report at the end of a run.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "hdfc_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"
BUNDLE_OUT = ROOT / "out" / "hdfc_bundle.json"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
LAST_DAY = ["", "31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"]

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill", "gsec"}
EQUITY_TYPES = {"equity", "reit"}

# A token is a "plan/option clause" (stripped from the base name, not part of the
# scheme identity) when every word in it — after removing digits/%/punctuation used
# in donation-split clauses like "50% IDCW Donation Option" — is drawn from this
# vocabulary. Word-level check (not a fixed set of whole-token patterns) because
# AMFI concatenates clauses inconsistently ("Direct Growth Plan" as one token,
# "Direct Plan-Growth" as two) — confirmed by inspection across HDFC's ~650 AMFI
# rows. "fund" is deliberately excluded — it's part of real scheme names.
PLAN_STOPWORDS = {
    "direct", "regular", "plan", "option", "options", "growth", "idcw", "dividend",
    "bonus", "quarterly", "monthly", "annual", "half", "yearly", "weekly", "daily",
    "segregated", "retail", "institutional", "income", "distribution", "cum",
    "capital", "withdrawal", "payout", "reinvestment", "reinvest", "donation",
}

# Known scheme renames where the xlsx portfolio-disclosure title and the AMFI NAV
# feed haven't been reconciled (confirmed by direct inspection — AMFI still lists
# the pre-rename name as of this build). Documented, not guessed: same AMC, same
# fund family, only the "flavour" word in the name changed.
SCHEME_NAME_ALIASES = {
    "HDFC Multi-Asset Allocation Fund": "HDFC Multi-Asset Fund",
    # Renamed ~March 2026 (confirmed: "Non-Cyclical Consumer Fund" appears in every
    # parsed month through 2026-02, "Consumption Fund" from 2026-03 on, never both
    # in the same month) — AMFI's feed only has the post-rename name.
    "HDFC Non-Cyclical Consumer Fund": "HDFC Consumption Fund",
    # A literal duplicated-text typo in HDFC's own July 2025 source file's row0/col0
    # ("...Multi-Asset Active FOF Asset Active FOF (Formerly known as HDFC Asset
    # Allocator Fund of Funds)") — confirmed by inspecting that one file directly.
    "HDFC Multi-Asset Active FOF Asset Active FOF": "HDFC Multi-Asset Active FOF",
    # Pre-2021/2022-era scheme names confirmed (via AMFI's HDFC section + HDFC's own
    # "formerly known as" disclosures) to be older names for schemes AMFI now lists
    # under a renamed identity — extending the archive back to 2021-04 surfaces these
    # for the first time (the original 13-month recent-only build never saw them).
    # Each was cross-checked against a plausible current AMFI counterpart before
    # aliasing — none guessed from name similarity alone.
    "HDFC Asset Allocator Fund of Fund": "HDFC Multi-Asset Active FOF",
    "HDFC Asset Allocator Fund of Funds": "HDFC Multi-Asset Active FOF",
    "HDFC Capital Builder Value Fund": "HDFC Value Fund",
    "HDFC Developed World Indexes Fund Of Funds": "HDFC Developed World Overseas Equity Passive FOF",
    "HDFC Dynamic PE Ratio Fund of Funds": "HDFC Balanced Advantage Fund",
    "HDFC Gold Exchange Traded Fund": "HDFC Gold ETF",
    "HDFC Gold Exchange Traded Fund.": "HDFC Gold ETF",
    "HDFC Growth Opportunities Fund": "HDFC Large and Mid Cap Fund",
    "HDFC Index Fund - BSE SENSEX Plan": "HDFC BSE Sensex Index Fund",
    "HDFC Index Fund-S&P BSE SENSEX Plan": "HDFC BSE Sensex Index Fund",
    "HDFC Index Fund-Sensex Plan": "HDFC BSE Sensex Index Fund",
    "HDFC Index Fund-NIFTY 50 Plan": "HDFC Nifty 50 Index Fund",
    "HDFC Mid-Cap Opportunities Fund": "HDFC Mid Cap Fund",
    "HDFC Childrens Gift Fund": "HDFC Childrens Fund",
    "HDFC NIFTY 50 Exchange Traded Fund": "HDFC NIFTY 50 ETF",
    "HDFC NIFTY BANK EXCHANGE TRADED FUND": "HDFC NIFTY Bank ETF",
    "HDFC NIFTY Bank Exchange Traded Fund": "HDFC NIFTY Bank ETF",
    "HDFC S&P BSE SENSEX Exchange Traded Fund": "HDFC BSE Sensex ETF",
    "HDFC S&P BSE SENSEX ETF": "HDFC BSE Sensex ETF",
    "HDFC Sensex Exchange Traded Fund": "HDFC BSE Sensex ETF",
    "HDFC Taxsaver Fund": "HDFC ELSS Tax saver",
    "HDFC Top 100 Fund": "HDFC Large Cap Fund",
    # En-dash ("–") separator variant of the SENSEX Index Fund plan name — the
    # trailing-parenthetical strip below removes "(AN OPEN-ENDED...)" but leaves
    # this base text, which still needs the same rename alias as the regular
    # hyphen variants above.
    "HDFC Index Fund – S&P BSE SENSEX Plan": "HDFC BSE Sensex Index Fund",
}

# Some older-era xlsx titles keep the "(An Open Ended ... Fund)" scheme-type
# parenthetical baked into row0/col0 that parse_hdfc_xlsx.find_fund_name()
# normally strips — confirmed cases where it didn't (e.g. an unusual "–" en-dash
# separator instead of the regular "(" the parser's regex expects right after a
# space) slip through as scheme_name here. A second, cheap strip at match time
# (before the exact/alias/fuzzy lookups) is a safety net, not a replacement for
# the parser-side fix — same "extension lies" defensive posture as the rest of
# this pipeline.
TRAILING_PAREN_RE = re.compile(r"\s*[\(\[].*$", re.DOTALL)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def is_plan_clause(token: str) -> bool:
    stripped = re.sub(r"[\d%]+", " ", token)
    words = [w.lower() for w in re.split(r"\s+", stripped) if w]
    if not words:
        return True
    return all(w in PLAN_STOPWORDS for w in words)


def split_amfi_name(full_name: str):
    """Strip trailing plan/option clauses (split on ' - ' or trailing '-') to recover
    the scheme's base name, plus whether this variant is Direct-Plan / Growth."""
    # AMFI formatting is inconsistent about spacing around '-' (e.g. "Fund- Direct
    # Plan-Growth" with no space before the dash) — split on any run of dashes.
    # Also collapse repeated internal whitespace (AMFI has real double-space typos,
    # e.g. "Nifty India Consumption Index  Fund").
    full_name = re.sub(r"\s{2,}", " ", full_name)
    parts = [p.strip() for p in re.split(r"\s*-\s*", full_name) if p.strip()]
    base_parts = []
    is_direct = False
    is_growth = False
    for p in parts:
        if is_plan_clause(p):
            pl = p.lower()
            if "direct" in pl:
                is_direct = True
            if "growth" in pl:
                is_growth = True
            continue
        base_parts.append(p)
    base_name = " - ".join(base_parts).strip()
    return base_name, is_direct, is_growth


def load_amfi_hdfc():
    """Returns {normalized_base_name: {"code", "isin", "display_name", "is_direct", "is_growth"}}."""
    lines = AMFI_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    in_hdfc = False
    candidates = {}  # norm(base_name) -> list of variant dicts
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            in_hdfc = "hdfc mutual fund" in line.lower()
            continue
        if not in_hdfc:
            continue
        fields = line.split(";")
        if len(fields) < 5:
            continue
        code, isin_growth, isin_reinvest, scheme_name, nav = fields[:5]
        base_name, is_direct, is_growth = split_amfi_name(scheme_name)
        if not base_name:
            continue
        key = norm(base_name)
        isin = isin_growth if isin_growth and isin_growth != "-" else (isin_reinvest if isin_reinvest != "-" else None)
        candidates.setdefault(key, []).append({
            "code": code, "isin": isin, "display_name": base_name,
            "is_direct": is_direct, "is_growth": is_growth,
        })

    best = {}
    for key, variants in candidates.items():
        def rank(v):
            return (v["is_direct"] and v["is_growth"], v["is_growth"], v["is_direct"])
        best[key] = max(variants, key=rank)
    return best


def match_scheme(scheme_name: str, amfi_index: dict, unmatched_log: list):
    # Alias lookup first (exact raw name, before any stripping — some aliases are
    # keyed on the untouched title including its parenthetical, e.g. the July 2025
    # duplicated-text typo above).
    lookup_name = SCHEME_NAME_ALIASES.get(scheme_name, scheme_name)
    key = norm(lookup_name)
    if key in amfi_index:
        return amfi_index[key]
    # Safety-net: strip a trailing "(...)"/"[...]" scheme-type description that
    # parse_hdfc_xlsx.find_fund_name() normally already removes — confirmed cases
    # (an en-dash separator instead of the expected pattern) let it slip through
    # to here. Re-check both plain and alias-mapped forms of the stripped name.
    stripped = TRAILING_PAREN_RE.sub("", lookup_name).strip()
    if stripped != lookup_name:
        stripped = SCHEME_NAME_ALIASES.get(stripped, stripped)
        key = norm(stripped)
        if key in amfi_index:
            return amfi_index[key]
    # Fuzzy fallback — HDFC's xlsx title occasionally drops connector words
    # ("HDFC Banking  Financial Services Fund" vs AMFI's "...Banking & Financial
    # Services Fund"). Conservative cutoff to avoid cross-scheme false matches.
    close = difflib.get_close_matches(key, amfi_index.keys(), n=1, cutoff=0.82)
    if close:
        return amfi_index[close[0]]
    unmatched_log.append(scheme_name)
    return None


CATEGORY_HINTS = [
    (re.compile(r"overnight", re.I), "Debt - Overnight Fund"),
    (re.compile(r"liquid", re.I), "Debt - Liquid Fund"),
    (re.compile(r"ultra short", re.I), "Debt - Ultra Short Duration Fund"),
    (re.compile(r"low duration", re.I), "Debt - Low Duration Fund"),
    (re.compile(r"money market", re.I), "Debt - Money Market Fund"),
    (re.compile(r"short term debt|short duration", re.I), "Debt - Short Duration Fund"),
    (re.compile(r"medium term|medium duration", re.I), "Debt - Medium Duration Fund"),
    (re.compile(r"corporate bond", re.I), "Debt - Corporate Bond Fund"),
    (re.compile(r"banking and psu|banking.*psu", re.I), "Debt - Banking and PSU Fund"),
    (re.compile(r"credit risk", re.I), "Debt - Credit Risk Fund"),
    (re.compile(r"gilt|g-?sec", re.I), "Debt - Gilt Fund"),
    (re.compile(r"floating rate", re.I), "Debt - Floater Fund"),
    (re.compile(r"dynamic debt|income fund", re.I), "Debt - Dynamic Bond Fund"),
    (re.compile(r"long duration", re.I), "Debt - Long Duration Fund"),
    (re.compile(r"\bfmp\b", re.I), "Debt - Fixed Maturity Plan"),
    (re.compile(r"arbitrage", re.I), "Hybrid - Arbitrage Fund"),
    (re.compile(r"equity savings", re.I), "Hybrid - Equity Savings Fund"),
    (re.compile(r"balanced advantage", re.I), "Hybrid - Balanced Advantage Fund"),
    (re.compile(r"multi-?asset", re.I), "Hybrid - Multi Asset Allocation Fund"),
    (re.compile(r"hybrid equity|hybrid.*fund$", re.I), "Hybrid - Aggressive Hybrid Fund"),
    (re.compile(r"retirement savings.*hybrid-debt", re.I), "Hybrid - Conservative Hybrid Fund"),
    (re.compile(r"retirement savings.*hybrid", re.I), "Hybrid - Aggressive Hybrid Fund"),
    (re.compile(r"gold etf fund of fund|gold etf.*fof", re.I), "Other - FoF (Gold)"),
    (re.compile(r"silver etf fund of fund|silver etf.*fof", re.I), "Other - FoF (Silver)"),
    (re.compile(r"gold etf", re.I), "Other - ETF (Gold)"),
    (re.compile(r"silver etf", re.I), "Other - ETF (Silver)"),
    (re.compile(r"overseas|developed world", re.I), "Other - FoF (Overseas)"),
    (re.compile(r"fund of fund|\bfof\b", re.I), "Other - FoF (Domestic)"),
    (re.compile(r"\betf\b", re.I), "Other - ETF"),
    (re.compile(r"index fund|nifty.*index", re.I), "Equity - Index Fund"),
    (re.compile(r"elss|tax saver", re.I), "Equity - ELSS"),
    (re.compile(r"large and mid|large.*mid cap", re.I), "Equity - Large & Mid Cap Fund"),
    (re.compile(r"large cap", re.I), "Equity - Large Cap Fund"),
    (re.compile(r"mid cap", re.I), "Equity - Mid Cap Fund"),
    (re.compile(r"small cap", re.I), "Equity - Small Cap Fund"),
    (re.compile(r"multi cap", re.I), "Equity - Multi Cap Fund"),
    (re.compile(r"flexi cap", re.I), "Equity - Flexi Cap Fund"),
    (re.compile(r"focused fund", re.I), "Equity - Focused Fund"),
    (re.compile(r"dividend yield", re.I), "Equity - Dividend Yield Fund"),
    (re.compile(r"value fund", re.I), "Equity - Value Fund"),
    (re.compile(r"contra", re.I), "Equity - Contra Fund"),
    (re.compile(r"mnc|manufacturing|technology|pharma|infrastructure|banking.*financial|"
                r"consumption|transportation|defence|housing|business cycle", re.I), "Equity - Sectoral/Thematic Fund"),
    (re.compile(r"children", re.I), "Solution Oriented - Children's Fund"),
]


def category_for(scheme_name: str) -> str:
    for pat, cat in CATEGORY_HINTS:
        if pat.search(scheme_name):
            return cat
    return "Equity - Other"


def asset_class_for(holdings, category: str):
    if not holdings:
        return "other"
    total = sum(h["weight"] for h in holdings) or 1
    eq_pct = sum(h["weight"] for h in holdings if h["type"] in EQUITY_TYPES) / total * 100
    if category.startswith("Debt") or category.startswith("Solution") and "debt" in category.lower():
        return "debt"
    if category.startswith("Hybrid"):
        return "hybrid"
    if category.startswith("Other"):
        return "other"
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
        elif h["type"] in ("fund", "derivative", "preference"):
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


def build_disclosure(scheme_name, period, bucket, ident):
    holdings = bucket["holdings"]
    total_weight = round(sum(h["weight"] for h in holdings), 2)
    top_holdings = sorted(holdings, key=lambda h: -h["weight"])[:10]
    deployable_cash = round(sum(h["weight"] for h in holdings if h["type"] in DEPLOYABLE_TYPES), 2)
    aum = round(sum(h["market_value_cr"] for h in holdings if h.get("market_value_cr") is not None), 2)
    year, month = period.split("-")
    category = category_for(scheme_name)
    data = {
        "amfi_code": ident["code"],
        "scheme_name": f"{scheme_name} - Direct Plan - Growth",
        "amc_name": "HDFC Mutual Fund",
        "category": category,
        "isin": ident["isin"] or "",
        "asset_class": asset_class_for(holdings, category),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{LAST_DAY[int(month)]}",
        "source_org": "HDFC Mutual Fund",
        "source_url": "https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure",
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
        "amfi_code": ident["code"],
        "amc_slug": "hdfc",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "HDFC Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }, category


def main():
    periods = sys.argv[1:]
    if not periods:
        periods = sorted(p.stem for p in OUT_DIR.glob("*.json"))
    if not periods:
        print("No parsed periods found in tools/out/hdfc_xlsx/. Run parse_all_hdfc_xlsx.py first.")
        return 1

    amfi_index = load_amfi_hdfc()
    print(f"AMFI: {len(amfi_index)} distinct HDFC base scheme names loaded.")

    amcs = [{"slug": "hdfc", "name": "HDFC Mutual Fund",
             "factsheet_url": "https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure",
             "archive_from": "2021-04", "status": "loaded"}]
    funds = []
    disclosures = []
    seen_funds = set()
    unmatched = set()
    matched_scheme_names = set()

    for period in periods:
        path = OUT_DIR / f"{period}.json"
        if not path.exists():
            print(f"skip {period}: not parsed yet")
            continue
        parsed = json.loads(path.read_text())
        for raw_scheme_name, bucket in parsed.items():
            log = []
            ident = match_scheme(raw_scheme_name, amfi_index, log)
            unmatched.update(log)
            if ident is None:
                continue
            matched_scheme_names.add(raw_scheme_name)
            # Use the alias target (if any) as the display name too, so a source
            # typo or old scheme name doesn't leak into scheme_name/category for
            # just the one month it appeared in — every period for this fund
            # should read identically.
            scheme_name = SCHEME_NAME_ALIASES.get(raw_scheme_name, raw_scheme_name)
            if ident["code"] not in seen_funds:
                category = category_for(scheme_name)
                funds.append({
                    "amc_slug": "hdfc",
                    "amfi_code": ident["code"],
                    "scheme_name": f"{scheme_name} - Direct Plan - Growth",
                    "isin_growth": ident["isin"],
                    "isin_reinvest": None,
                    "category": category,
                    "asset_class": asset_class_for(bucket["holdings"], category),
                    "plan_type": "direct-growth",
                })
                seen_funds.add(ident["code"])
            disclosure, _ = build_disclosure(scheme_name, period, bucket, ident)
            disclosures.append(disclosure)

    bundle = {"amcs": amcs, "funds": funds, "disclosures": disclosures}
    BUNDLE_OUT.write_text(json.dumps(bundle, indent=2))
    print(f"{len(funds)} funds, {len(disclosures)} disclosures -> {BUNDLE_OUT}")
    print(f"{len(matched_scheme_names)} distinct scheme names matched to AMFI identity.")
    if unmatched:
        print(f"\n{len(unmatched)} scheme names UNMATCHED to any AMFI code (dropped, not guessed):")
        for u in sorted(unmatched):
            print("  -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
