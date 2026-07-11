#!/usr/bin/env python3
"""Join parsed Invesco periods (tools/out/invesco_xlsx/<period>.json — from
parse_all_invesco_xlsx.py) with AMFI identity into the app's AnalyseData
contract, and emit tools/out/invesco_bundle.json in the same {amcs, funds,
disclosures} shape as ppfas_bundle.json / hdfc_bundle.json (amc_slug:
"invesco" throughout). Mirrors build_dataset_hdfc.py's structure closely —
same AMFI name-matching strategy (many schemes, not a small hardcoded dict
like build_dataset.py's 7 PPFAS funds).

AMFI scheme names encode plan/option as trailing " - <clause>" segments
(e.g. "Invesco India Liquid Fund - Direct Plan - Growth"). Strategy: for
every AMFI row under the "Invesco Mutual Fund" section, strip known plan/
option clauses to recover the scheme's base name, keep the best-ranked
variant per base name (Direct+Growth > Growth-only > first seen), then
match each parsed xlsx scheme name to a base name by normalized exact
match, falling back to a fuzzy best-match (difflib) above a conservative
cutoff. Anything that still doesn't match is logged and DROPPED (never
guessed) — see the "unmatched" report at the end of a run.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "invesco_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"
BUNDLE_OUT = ROOT / "out" / "invesco_bundle.json"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
LAST_DAY = ["", "31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"]

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill", "gsec"}
EQUITY_TYPES = {"equity", "reit"}

# Same word-level "plan/option clause" stopword check as build_dataset_hdfc.py —
# a token is stripped from the base name only when every word in it is drawn
# from this vocabulary (confirmed against Invesco's ~250 AMFI rows).
PLAN_STOPWORDS = {
    "direct", "regular", "plan", "option", "options", "growth", "idcw", "dividend",
    "bonus", "quarterly", "monthly", "annual", "half", "yearly", "weekly", "daily",
    "segregated", "retail", "institutional", "income", "distribution", "cum",
    "capital", "withdrawal", "payout", "reinvestment", "reinvest", "donation",
    "discretionary", "unclaimed", "above", "below", "years", "year", "b",
}

# Known scheme renames where the xlsx portfolio-disclosure title and the AMFI
# NAV feed haven't been reconciled — same documented (not guessed) pattern as
# build_dataset_hdfc.py's SCHEME_NAME_ALIASES. Confirmed by direct inspection
# of a 2019 sample file: "Invesco India Tax Plan" is the pre-rename name for
# the scheme AMFI now lists as "Invesco India ELSS Tax Saver Fund" (SEBI's
# 2018 ELSS-category renaming round) — see parse_invesco_xlsx.py's
# find_fund_name docstring.
SCHEME_NAME_ALIASES = {
    "Invesco India Tax Plan": "Invesco India ELSS Tax Saver Fund",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def is_plan_clause(token: str) -> bool:
    stripped = re.sub(r"[\d%]+", " ", token)
    words = [w.lower() for w in re.split(r"\s+", stripped) if w]
    if not words:
        return True
    return all(w in PLAN_STOPWORDS for w in words)


def split_amfi_name(full_name: str):
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


def load_amfi_invesco():
    """Returns {normalized_base_name: {"code", "isin", "display_name", "is_direct", "is_growth"}}."""
    lines = AMFI_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    in_invesco = False
    candidates = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            in_invesco = "invesco mutual fund" in line.lower()
            continue
        if not in_invesco:
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
    lookup_name = SCHEME_NAME_ALIASES.get(scheme_name, scheme_name)
    key = norm(lookup_name)
    if key in amfi_index:
        return amfi_index[key]
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
    (re.compile(r"floating rate|floater", re.I), "Debt - Floater Fund"),
    (re.compile(r"dynamic bond|income fund", re.I), "Debt - Dynamic Bond Fund"),
    (re.compile(r"long duration", re.I), "Debt - Long Duration Fund"),
    (re.compile(r"\bfmp\b|fixed maturity", re.I), "Debt - Fixed Maturity Plan"),
    (re.compile(r"arbitrage", re.I), "Hybrid - Arbitrage Fund"),
    (re.compile(r"equity savings", re.I), "Hybrid - Equity Savings Fund"),
    (re.compile(r"balanced advantage", re.I), "Hybrid - Balanced Advantage Fund"),
    (re.compile(r"multi-?asset", re.I), "Hybrid - Multi Asset Allocation Fund"),
    (re.compile(r"conservative hybrid", re.I), "Hybrid - Conservative Hybrid Fund"),
    (re.compile(r"aggressive hybrid|hybrid equity", re.I), "Hybrid - Aggressive Hybrid Fund"),
    (re.compile(r"gold etf fund of fund|gold.*fof", re.I), "Other - FoF (Gold)"),
    (re.compile(r"silver etf fund of fund|silver.*fof", re.I), "Other - FoF (Silver)"),
    (re.compile(r"gold.*exchange traded|gold etf", re.I), "Other - ETF (Gold)"),
    (re.compile(r"silver.*exchange traded|silver etf", re.I), "Other - ETF (Silver)"),
    (re.compile(r"pan european|global equity income|overseas|developed|international opportunities", re.I), "Other - FoF (Overseas)"),
    (re.compile(r"fund of fund|\bfof\b", re.I), "Other - FoF (Domestic)"),
    (re.compile(r"exchange traded fund|\betf\b", re.I), "Other - ETF"),
    (re.compile(r"index fund|nifty.*index|sensex.*index", re.I), "Equity - Index Fund"),
    (re.compile(r"elss|tax saver|tax plan", re.I), "Equity - ELSS"),
    (re.compile(r"large and mid|large.*mid ?cap", re.I), "Equity - Large & Mid Cap Fund"),
    (re.compile(r"large cap|bluechip", re.I), "Equity - Large Cap Fund"),
    (re.compile(r"mid ?cap", re.I), "Equity - Mid Cap Fund"),
    (re.compile(r"small ?cap", re.I), "Equity - Small Cap Fund"),
    (re.compile(r"multi ?cap", re.I), "Equity - Multi Cap Fund"),
    (re.compile(r"flexi ?cap", re.I), "Equity - Flexi Cap Fund"),
    (re.compile(r"focused fund", re.I), "Equity - Focused Fund"),
    (re.compile(r"dividend yield", re.I), "Equity - Dividend Yield Fund"),
    (re.compile(r"value fund", re.I), "Equity - Value Fund"),
    (re.compile(r"contra", re.I), "Equity - Contra Fund"),
    (re.compile(r"infrastructure|technology|financial services|manufactur|pharma|consumption|psu", re.I), "Equity - Sectoral/Thematic Fund"),
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
    if category.startswith("Debt"):
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
        "amc_name": "Invesco Mutual Fund",
        "category": category,
        "isin": ident["isin"] or "",
        "asset_class": asset_class_for(holdings, category),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{LAST_DAY[int(month)]}",
        "source_org": "Invesco Mutual Fund",
        "source_url": "https://invescomutualfund.com/literature-and-form?tab=Complete",
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
        "amc_slug": "invesco",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "Invesco Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }, category


def main():
    periods = sys.argv[1:]
    if not periods:
        periods = sorted(p.stem for p in OUT_DIR.glob("*.json"))
    if not periods:
        print("No parsed periods found in tools/out/invesco_xlsx/. Run parse_all_invesco_xlsx.py first.")
        return 1

    amfi_index = load_amfi_invesco()
    print(f"AMFI: {len(amfi_index)} distinct Invesco base scheme names loaded.")

    amcs = [{"slug": "invesco", "name": "Invesco Mutual Fund",
             "factsheet_url": "https://invescomutualfund.com/literature-and-form?tab=Complete",
             "archive_from": "2012-09", "status": "loaded"}]
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
            scheme_name = SCHEME_NAME_ALIASES.get(raw_scheme_name, raw_scheme_name)
            if ident["code"] not in seen_funds:
                category = category_for(scheme_name)
                funds.append({
                    "amc_slug": "invesco",
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
