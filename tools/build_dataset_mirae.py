#!/usr/bin/env python3
"""Join parsed Mirae periods (tools/out/mirae_xlsx/<period>.json — from
parse_all_mirae_xlsx.py) with AMFI identity into the app's AnalyseData
contract, and emit tools/out/mirae_bundle.json in the same {amcs, funds,
disclosures} shape as ppfas_bundle.json/hdfc_bundle.json (amc_slug: "mirae"
throughout).

Like HDFC (100+ schemes), Mirae needs a name-matching pass against
cache/amfi_nav.txt rather than a small hardcoded dict (PPFAS's 7-scheme
approach). Reuses build_dataset_hdfc.py's overall strategy (strip
plan/option clauses off each AMFI row to recover a base scheme name, exact
match, difflib fallback, log+drop anything unmatched) but with a more
general clause-stripper: HDFC's AMFI rows are consistently dash-delimited
("HDFC Flexi Cap Fund - Growth Option - Direct Plan"); Mirae's are NOT —
confirmed by inspecting cache/amfi_nav.txt directly, e.g. "Mirae Asset
Arbitrage Fund Direct Growth" and "Mirae Asset Dynamic Bond Fund -Direct
Plan -Growth" both appear, dash and space delimited inconsistently, even for
the same base scheme. Fix: normalize all dashes to spaces first, then strip
a trailing RUN of plan/option stopwords word-by-word (not clause-by-clause)
from the end of the name — order-independent of whether the source used a
dash or a space to separate them.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "mirae_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"
BUNDLE_OUT = ROOT / "out" / "mirae_bundle.json"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
LAST_DAY = ["", "31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"]

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill"}
EQUITY_TYPES = {"equity", "reit"}

# Same vocabulary as build_dataset_hdfc.py's PLAN_STOPWORDS (word-level, not a
# fixed set of whole clauses) — "fund" deliberately excluded, it's part of real
# scheme names.
PLAN_STOPWORDS = {
    "direct", "regular", "plan", "option", "options", "growth", "idcw", "dividend",
    "bonus", "quarterly", "monthly", "annual", "half", "yearly", "weekly", "daily",
    "segregated", "retail", "institutional", "income", "distribution", "cum",
    "capital", "withdrawal", "payout", "reinvestment", "reinvest", "donation",
}

# Known xlsx-title vs AMFI-feed name drift, confirmed by inspection — same AMC,
# same fund, only cosmetic differences (spelling/expansion of "FOF", stray
# duplicated "Mirae Asset" prefix, ampersand vs "and", hyphen placement).
SCHEME_NAME_ALIASES = {
    "Mirae Asset Mirae Asset Nifty India New Age Consumption ETF": "Mirae Asset Nifty India New Age Consumption ETF",
    "Mirae Asset Global Electric  Autonomous Vehicles ETFs Fund of Fund": "Mirae Asset Global Electric & Autonomous Vehicles ETFs Fund of Fund",
    # Renamed within the archive window — AMFI's feed only has the post-rename
    # name, confirmed by inspection (old name never appears alongside the new
    # one in the same month; parse_mirae_xlsx.py's find_fund_name() already
    # strips the "(Formerly Known as ...)" suffix these renamed schemes carry
    # in their own row0 cell, this alias only covers the handful of MONTHS that
    # predate the rename entirely, where the cell was just the old name).
    "Mirae Asset Equity Allocator Fund of Fund": "Mirae Asset Diversified Equity Allocator Passive FOF",
    "Mirae Asset Global Electric & Autonomous Vehicles ETFs Fund of Fund": "Mirae Asset Global Electric & Autonomous Vehicles Equity Passive FOF",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def split_amfi_name(full_name: str):
    """Strip a trailing run of plan/option words (dash- or space-delimited,
    see module docstring) to recover the scheme's base name."""
    normalized = re.sub(r"[-–—]", " ", full_name)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    words = normalized.split(" ")
    is_direct = False
    is_growth = False
    cut = len(words)
    for i in range(len(words) - 1, -1, -1):
        w = re.sub(r"[^a-zA-Z]", "", words[i]).lower()
        if w in PLAN_STOPWORDS:
            if w == "direct":
                is_direct = True
            if w == "growth":
                is_growth = True
            cut = i
            continue
        break
    base_name = " ".join(words[:cut]).strip()
    return base_name, is_direct, is_growth


def load_amfi_mirae():
    """Returns {normalized_base_name: {"code", "isin", "display_name", "is_direct", "is_growth"}}."""
    lines = AMFI_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    in_mirae = False
    candidates = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            in_mirae = "mirae asset mutual fund" in line.lower()
            continue
        if not in_mirae:
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
    (re.compile(r"short (term|duration)", re.I), "Debt - Short Duration Fund"),
    (re.compile(r"medium (term|duration)", re.I), "Debt - Medium Duration Fund"),
    (re.compile(r"corporate bond", re.I), "Debt - Corporate Bond Fund"),
    (re.compile(r"banking and psu|banking.*psu", re.I), "Debt - Banking and PSU Fund"),
    (re.compile(r"credit risk", re.I), "Debt - Credit Risk Fund"),
    (re.compile(r"gilt|g-?sec", re.I), "Debt - Gilt Fund"),
    (re.compile(r"dynamic bond", re.I), "Debt - Dynamic Bond Fund"),
    (re.compile(r"long duration", re.I), "Debt - Long Duration Fund"),
    (re.compile(r"\bfmp\b|fixed maturity", re.I), "Debt - Fixed Maturity Plan"),
    (re.compile(r"sdl|index fund", re.I), "Debt - Index Fund"),
    (re.compile(r"arbitrage", re.I), "Hybrid - Arbitrage Fund"),
    (re.compile(r"equity savings", re.I), "Hybrid - Equity Savings Fund"),
    (re.compile(r"balanced advantage", re.I), "Hybrid - Balanced Advantage Fund"),
    (re.compile(r"multi asset", re.I), "Hybrid - Multi Asset Allocation Fund"),
    (re.compile(r"aggressive hybrid", re.I), "Hybrid - Aggressive Hybrid Fund"),
    (re.compile(r"conservative hybrid", re.I), "Hybrid - Conservative Hybrid Fund"),
    (re.compile(r"gold.*silver|silver.*gold", re.I), "Other - FoF (Gold & Silver)"),
    (re.compile(r"gold etf fund of fund|gold.*fof", re.I), "Other - FoF (Gold)"),
    (re.compile(r"silver etf fund of fund|silver.*fof", re.I), "Other - FoF (Silver)"),
    (re.compile(r"gold etf", re.I), "Other - ETF (Gold)"),
    (re.compile(r"silver etf", re.I), "Other - ETF (Silver)"),
    (re.compile(r"hang seng|nyse fang|nasdaq|s&p 500|global x|electric.*autonomous|overseas", re.I), "Other - FoF (Overseas)"),
    (re.compile(r"fund of fund|\bfof\b", re.I), "Other - FoF (Domestic)"),
    (re.compile(r"\betf\b", re.I), "Other - ETF"),
    (re.compile(r"index fund|nifty.*index", re.I), "Equity - Index Fund"),
    (re.compile(r"elss|tax saver", re.I), "Equity - ELSS"),
    (re.compile(r"large\s*&?\s*mid ?cap", re.I), "Equity - Large & Mid Cap Fund"),
    (re.compile(r"large cap", re.I), "Equity - Large Cap Fund"),
    (re.compile(r"mid ?cap", re.I), "Equity - Mid Cap Fund"),
    (re.compile(r"small ?cap", re.I), "Equity - Small Cap Fund"),
    (re.compile(r"multi ?cap", re.I), "Equity - Multi Cap Fund"),
    (re.compile(r"flexi cap", re.I), "Equity - Flexi Cap Fund"),
    (re.compile(r"focused fund", re.I), "Equity - Focused Fund"),
    (re.compile(r"value fund", re.I), "Equity - Value Fund"),
    (re.compile(r"great consumer|consumption", re.I), "Equity - Sectoral/Thematic Fund"),
    (re.compile(r"banking and financial services|infrastructure|healthcare|defence|"
                r"manufacturing|technology|pharma", re.I), "Equity - Sectoral/Thematic Fund"),
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


def build_metrics(raw_metrics):
    if not raw_metrics:
        return None
    return {
        "ytm": raw_metrics.get("ytm"),
        "macaulay_days": raw_metrics.get("macaulay_days"),
        "residual_days": raw_metrics.get("residual_days"),
        "benchmark": raw_metrics.get("benchmark"),
        "inception": raw_metrics.get("inception"),
        "fund_managers": raw_metrics.get("fund_managers"),
    }


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
        "amc_name": "Mirae Asset Mutual Fund",
        "category": category,
        "isin": ident["isin"] or "",
        "asset_class": asset_class_for(holdings, category),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{LAST_DAY[int(month)]}",
        "source_org": "Mirae Asset Mutual Fund",
        "source_url": "https://www.miraeassetmf.co.in/downloads/portfolio",
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
        "metrics": build_metrics(bucket.get("metrics")),
    }
    return {
        "amfi_code": ident["code"],
        "amc_slug": "mirae",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "Mirae Asset Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }, category


def main():
    periods = sys.argv[1:]
    if not periods:
        periods = sorted(p.stem for p in OUT_DIR.glob("*.json"))
    if not periods:
        print("No parsed periods found in tools/out/mirae_xlsx/. Run parse_all_mirae_xlsx.py first.")
        return 1

    amfi_index = load_amfi_mirae()
    print(f"AMFI: {len(amfi_index)} distinct Mirae base scheme names loaded.")

    amcs = [{"slug": "mirae", "name": "Mirae Asset Mutual Fund",
             "factsheet_url": "https://www.miraeassetmf.co.in/downloads/portfolio",
             "archive_from": "2012-11", "status": "loaded"}]
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
                    "amc_slug": "mirae",
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
