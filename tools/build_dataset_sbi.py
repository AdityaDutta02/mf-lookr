#!/usr/bin/env python3
"""Join parsed SBI periods (tools/out/sbi_xlsx/<period>.json — from
parse_all_sbi_xlsx.py) with AMFI identity into the app's AnalyseData
contract, and emit tools/out/sbi_bundle.json in the same {amcs, funds,
disclosures} shape as ppfas_bundle.json / hdfc_bundle.json (amc_slug: "sbi"
throughout).

Mirrors build_dataset_hdfc.py's approach exactly (SBI has 100+ schemes too —
no small hardcoded dict like PPFAS's build_dataset.py). Strategy: for every
AMFI row under the "SBI Mutual Fund" section, strip known plan/option
clauses to recover the scheme's base name, keep the best-ranked variant per
base name (Direct+Growth > Growth-only > first seen), then match each parsed
xlsx scheme name (read from the file's own "SCHEME NAME :" cell by
parse_sbi_xlsx.py — never the discovery manifest's link-text title) to a
base name by normalized exact match, falling back to a fuzzy best-match
(difflib) above a conservative cutoff. Anything that still doesn't match is
logged and DROPPED (never guessed) — see the "unmatched" report at the end
of a run.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "sbi_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"
BUNDLE_OUT = ROOT / "out" / "sbi_bundle.json"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
LAST_DAY = ["", "31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"]

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill", "gsec"}
EQUITY_TYPES = {"equity", "reit"}

# Same word-level heuristic as build_dataset_hdfc.py's PLAN_STOPWORDS — a clause is a
# plan/option marker (not part of scheme identity) when every word in it is drawn from
# this vocabulary. "fund" deliberately excluded — it's part of real scheme names.
PLAN_STOPWORDS = {
    "direct", "regular", "plan", "plna", "option", "options", "growth", "idcw", "dividend",
    "bonus", "quarterly", "monthly", "annual", "half", "yearly", "weekly", "daily",
    "segregated", "retail", "institutional", "income", "distribution", "cum",
    "capital", "withdrawal", "payout", "reinvestment", "reinvest", "donation",
}

# SBI's own xlsx "SCHEME NAME :" cell often self-documents a rename, e.g. "SBI
# Children's Fund - Investment Plan (Erstwhile known as SBI Magnum Children's Benefit
# Fund- IP)", "SBI ESG Exclusionary Strategy Fund (Previously known as SBI Magnum
# Equity ESG Fund)", or — confirmed in older (2019-2021) files — square brackets
# instead of parens: "SBI Flexicap Fund [earlier known as SBI Magnum Multicap Fund]".
# Stripping this trailing annotation (either bracket style, any of the three phrasings
# seen) recovers AMFI's CURRENT name directly, no alias table entry needed for these.
ERSTWHILE_SUFFIX_RE = re.compile(
    r"\s*[\(\[](?:erstwhile|previously|earlier)\s+known\s+as[^)\]]*[\)\]]\s*$", re.IGNORECASE
)

# Genuine renames where the OLDER xlsx months use the bare pre-rename name with no
# "(Erstwhile known as ...)" annotation at all (that annotation only started
# appearing in SBI's own files after the rename, not retroactively on old months) —
# confirmed by cross-checking each of these against AMFI's current SBI scheme list
# (see the "unmatched" report before/after this dict was added). SBI dropped the
# "Magnum" prefix from many scheme names industry-wide over the 2019-2026 range, and
# renamed most ETFs from "SBI-ETF <Index>" to "SBI <Index> ETF"; "Blue Chip Fund" ->
# "Large Cap Fund", "Long Term Equity Fund"/"Magnum Taxgain Scheme" -> "ELSS Tax Saver
# Fund" are SEBI/AMFI category-naming-standardization renames, same kind of drift
# HDFC's SCHEME_NAME_ALIASES documents. Schemes with NO current AMFI entry at all
# (closed-ended/merged/discontinued/matured — e.g. every "SBI Debt Fund Series B-*"
# FMP, "SBI Capital Protection Oriented Fund Series A", "SBI Magnum Global Fund",
# "SBI Resurgent India Opportunities Scheme", "SBI International Access- US Equity
# FoF", the pre-split single "SBI Magnum Children's Benefit Fund" before it became two
# separate Investment/Savings plans) are deliberately left OUT of this table and stay
# in the "unmatched" (dropped) report — no guessing their identity.
SCHEME_NAME_ALIASES = {
    "SBI Blue Chip Fund": "SBI Large Cap Fund",
    "SBI ETF Consumption": "SBI Nifty Consumption ETF",
    "SBI Long Term Equity Fund": "SBI ELSS Tax Saver Fund",
    "SBI Magnum Children's Benefit Fund - Savings Plan": "SBI Children's Fund - Savings Plan",
    "SBI Magnum Comma Fund": "SBI Comma Fund",
    "SBI Magnum Constant Maturity Fund": "SBI Constant Maturity 10 Year Gilt Fund",
    "SBI Magnum Equity ESG Fund": "SBI ESG Exclusionary Strategy Fund",
    "SBI Magnum Gilt Fund": "SBI Gilt Fund",
    "SBI Magnum Income Fund": "SBI Medium to Long Duration Fund",
    "SBI Magnum Midcap Fund": "SBI Midcap Fund",
    "SBI Magnum Taxgain Scheme": "SBI ELSS Tax Saver Fund",
    "SBI-ETF 10 Year Gilt": "SBI Nifty 10 yr Benchmark G-Sec ETF",
    "SBI-ETF BSE 100": "SBI BSE 100 ETF",
    "SBI-ETF Gold": "SBI Gold ETF",
    "SBI-ETF IT": "SBI Nifty IT ETF",
    "SBI-ETF Nifty 50": "SBI Nifty 50 ETF",
    "SBI-ETF Nifty Bank": "SBI Nifty Bank ETF",
    "SBI-ETF Private Bank": "SBI Nifty Private Bank ETF",
    "SBI-ETF Quality": "SBI Nifty 200 Quality 30 ETF",
    "SBI-ETF Sensex": "SBI BSE Sensex ETF",
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


def load_amfi_sbi():
    """Returns {normalized_base_name: {"code", "isin", "display_name", "is_direct", "is_growth"}}."""
    lines = AMFI_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    in_sbi = False
    candidates = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            in_sbi = "sbi mutual fund" in line.lower()
            continue
        if not in_sbi:
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
    # Strip a self-documented "(Erstwhile known as ...)" / "(Previously known as ...)"
    # suffix FIRST — see ERSTWHILE_SUFFIX_RE's docstring — before falling back to the
    # explicit alias table for renames that predate that annotation appearing at all.
    stripped_name = ERSTWHILE_SUFFIX_RE.sub("", scheme_name).strip()
    lookup_name = SCHEME_NAME_ALIASES.get(stripped_name, stripped_name)
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
    (re.compile(r"short term debt|short duration|savings fund", re.I), "Debt - Short Duration Fund"),
    (re.compile(r"medium term|medium duration|magnum income", re.I), "Debt - Medium Duration Fund"),
    (re.compile(r"corporate bond", re.I), "Debt - Corporate Bond Fund"),
    (re.compile(r"banking and psu|banking.*psu", re.I), "Debt - Banking and PSU Fund"),
    (re.compile(r"credit risk", re.I), "Debt - Credit Risk Fund"),
    (re.compile(r"magnum gilt|gilt|g-?sec", re.I), "Debt - Gilt Fund"),
    (re.compile(r"floating rate|floater", re.I), "Debt - Floater Fund"),
    (re.compile(r"dynamic (bond|debt)|magnum income", re.I), "Debt - Dynamic Bond Fund"),
    (re.compile(r"long duration", re.I), "Debt - Long Duration Fund"),
    (re.compile(r"\bfmp\b|fixed maturity", re.I), "Debt - Fixed Maturity Plan"),
    (re.compile(r"debt fund series|capital protection", re.I), "Debt - Close Ended"),
    (re.compile(r"arbitrage", re.I), "Hybrid - Arbitrage Fund"),
    (re.compile(r"equity savings", re.I), "Hybrid - Equity Savings Fund"),
    (re.compile(r"balanced advantage", re.I), "Hybrid - Balanced Advantage Fund"),
    (re.compile(r"multi-?asset", re.I), "Hybrid - Multi Asset Allocation Fund"),
    (re.compile(r"equity hybrid|hybrid.*fund$", re.I), "Hybrid - Aggressive Hybrid Fund"),
    (re.compile(r"conservative hybrid|regular savings", re.I), "Hybrid - Conservative Hybrid Fund"),
    (re.compile(r"gold etf fund of fund|gold etf.*fof", re.I), "Other - FoF (Gold)"),
    (re.compile(r"silver etf fund of fund|silver etf.*fof", re.I), "Other - FoF (Silver)"),
    (re.compile(r"gold etf|gold fund", re.I), "Other - ETF (Gold)"),
    (re.compile(r"silver etf|silver fund", re.I), "Other - ETF (Silver)"),
    (re.compile(r"overseas|international|global|us equity|emerging", re.I), "Other - FoF (Overseas)"),
    (re.compile(r"fund of fund|\bfof\b", re.I), "Other - FoF (Domestic)"),
    (re.compile(r"\betf\b", re.I), "Other - ETF"),
    (re.compile(r"index fund|nifty.*index|sensex.*index", re.I), "Equity - Index Fund"),
    (re.compile(r"long term equity|tax saver|elss", re.I), "Equity - ELSS"),
    (re.compile(r"large and mid|large.*mid cap", re.I), "Equity - Large & Mid Cap Fund"),
    (re.compile(r"blue chip|large cap|magnum equity", re.I), "Equity - Large Cap Fund"),
    (re.compile(r"magnum midcap|mid ?cap", re.I), "Equity - Mid Cap Fund"),
    (re.compile(r"small ?cap", re.I), "Equity - Small Cap Fund"),
    (re.compile(r"multicap|multi ?cap", re.I), "Equity - Multi Cap Fund"),
    (re.compile(r"flexicap|flexi ?cap", re.I), "Equity - Flexi Cap Fund"),
    (re.compile(r"focused equity|focused fund", re.I), "Equity - Focused Fund"),
    (re.compile(r"dividend yield", re.I), "Equity - Dividend Yield Fund"),
    (re.compile(r"contra", re.I), "Equity - Contra Fund"),
    (re.compile(r"value fund", re.I), "Equity - Value Fund"),
    (re.compile(r"psu|healthcare|pharma|technology|infrastructure|banking.*financial|"
                r"consumption|automotive|energy opportunities|\bcomma\b|infotech|"
                r"fmcg|manufacturing|\bmnc\b", re.I), "Equity - Sectoral/Thematic Fund"),
    (re.compile(r"children", re.I), "Solution Oriented - Children's Fund"),
    (re.compile(r"retirement", re.I), "Solution Oriented - Retirement Fund"),
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
    if category.startswith("Debt") or (category.startswith("Solution") and "debt" in category.lower()):
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
        "amc_name": "SBI Mutual Fund",
        "category": category,
        "isin": ident["isin"] or "",
        "asset_class": asset_class_for(holdings, category),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{LAST_DAY[int(month)]}",
        "source_org": "SBI Mutual Fund",
        "source_url": "https://www.sbimf.com/portfolios",
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
        "amc_slug": "sbi",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "SBI Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }, category


def main():
    periods = sys.argv[1:]
    if not periods:
        periods = sorted(p.stem for p in OUT_DIR.glob("*.json"))
    if not periods:
        print("No parsed periods found in tools/out/sbi_xlsx/. Run parse_all_sbi_xlsx.py first.")
        return 1

    amfi_index = load_amfi_sbi()
    print(f"AMFI: {len(amfi_index)} distinct SBI base scheme names loaded.")

    amcs = [{"slug": "sbi", "name": "SBI Mutual Fund",
             "factsheet_url": "https://www.sbimf.com/portfolios",
             "archive_from": "2019-01", "status": "loaded"}]
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
            # Same stripped-then-aliased resolution as match_scheme(), so a source
            # "(Erstwhile known as ...)" annotation (present in SOME months for a
            # renamed scheme but not others — see ERSTWHILE_SUFFIX_RE's docstring)
            # never leaks into the stored scheme_name for just the months it happens
            # to appear in; every period for this fund reads identically.
            stripped_raw_name = ERSTWHILE_SUFFIX_RE.sub("", raw_scheme_name).strip()
            scheme_name = SCHEME_NAME_ALIASES.get(stripped_raw_name, stripped_raw_name)
            if ident["code"] not in seen_funds:
                category = category_for(scheme_name)
                funds.append({
                    "amc_slug": "sbi",
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
