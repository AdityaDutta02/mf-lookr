#!/usr/bin/env python3
"""Join a parsed PPFAS period (tools/out/ppfas_xlsx/<period>.json — from the
"Detailed Portfolio Disclosure" XLS, NOT the factsheet PDF; see
parse_ppfas_xlsx.py) with AMFI identity into the app's AnalyseData contract,
and emit a bundle the app's seed route can insert directly (amcs / funds /
disclosures rows).

Deterministic derivation only — no AI, no guessed numbers. Each holding's own
ISIN and quantity now come straight from the source XLS (the factsheet PDF
this rebuild used originally has neither — see parse_ppfas.py docstring).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "ppfas_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# canonical fund name -> AMFI scheme code we treat as this fund's primary identity
# (Direct Plan Growth — holdings/portfolio are plan-agnostic, this is just the ID).
AMFI_IDENTITY = {
    "Parag Parikh Flexi Cap Fund": {"code": "122639", "isin": "INF879O01027"},
    "Parag Parikh ELSS Tax Saver Fund": {"code": "147481", "isin": "INF879O01100"},
    "Parag Parikh Large Cap Fund": {"code": "154155", "isin": "INF879O01332"},
    "Parag Parikh Dynamic Asset Allocation Fund": {"code": "152468", "isin": "INF879O01266"},
    "Parag Parikh Conservative Hybrid Fund": {"code": "148958", "isin": "INF879O01175"},
    "Parag Parikh Arbitrage Fund": {"code": "152109", "isin": "INF879O01225"},
    "Parag Parikh Liquid Fund": {"code": "143269", "isin": "INF879O01068"},
}
CATEGORY = {
    "Parag Parikh Flexi Cap Fund": "Equity - Flexi Cap Fund",
    "Parag Parikh ELSS Tax Saver Fund": "Equity - ELSS",
    "Parag Parikh Large Cap Fund": "Equity - Large Cap Fund",
    "Parag Parikh Dynamic Asset Allocation Fund": "Hybrid - Dynamic Asset Allocation",
    "Parag Parikh Conservative Hybrid Fund": "Hybrid - Conservative Hybrid Fund",
    "Parag Parikh Arbitrage Fund": "Hybrid - Arbitrage Fund",
    "Parag Parikh Liquid Fund": "Debt - Liquid Fund",
}

DEPLOYABLE_TYPES = {"treps", "cash", "cd", "cp", "tbill"}
EQUITY_TYPES = {"equity", "reit"}


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
        # xlrd can hand back a numeric cell (e.g. an empty/stray rating cell) instead of
        # a string for "industry" — coerce before stripping.
        raw = h.get("industry")
        key = (str(raw).strip() if raw else "") or "Unclassified"
        agg[key] = agg.get(key, 0.0) + h["weight"]
    rows = sorted(({"name": k, "weight": round(v, 2)} for k, v in agg.items()), key=lambda r: -r["weight"])
    return rows[:top_n]


def build_disclosure(canonical_name, period, bucket):
    holdings = bucket["holdings"]
    ident = AMFI_IDENTITY[canonical_name]
    total_weight = round(sum(h["weight"] for h in holdings), 2)
    top_holdings = sorted(holdings, key=lambda h: -h["weight"])[:10]
    deployable_cash = round(sum(h["weight"] for h in holdings if h["type"] in DEPLOYABLE_TYPES), 2)
    # AUM = sum of every holding's disclosed market value — direct from the source XLS,
    # no text-parsing needed (unlike the old factsheet-PDF path).
    aum = round(sum(h["market_value_cr"] for h in holdings if h.get("market_value_cr") is not None), 2)
    year, month = period.split("-")
    data = {
        "amfi_code": ident["code"],
        "scheme_name": f"{canonical_name} - Direct Plan - Growth",
        "amc_name": "PPFAS Mutual Fund",
        "category": CATEGORY[canonical_name],
        "isin": ident["isin"],
        "asset_class": asset_class_for(holdings),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{['31','28','31','30','31','30','31','31','30','31','30','31'][int(month)-1]}",
        "source_org": "PPFAS Mutual Fund",
        "source_url": f"https://amc.ppfas.com/downloads/portfolio-disclosure/{year}/",
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
        "amc_slug": "ppfas",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "PPFAS Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }


def main():
    periods = sys.argv[1:] or ["2026-05"]
    amcs = [{"slug": "ppfas", "name": "PPFAS Mutual Fund", "factsheet_url": "https://amc.ppfas.com/downloads/factsheet/", "archive_from": "2013-06", "status": "loaded"}]
    funds = []
    disclosures = []
    seen_funds = set()

    for period in periods:
        path = OUT_DIR / f"{period}.json"
        if not path.exists():
            print(f"skip {period}: not parsed yet")
            continue
        parsed = json.loads(path.read_text())
        for canonical_name, bucket in parsed.items():
            if canonical_name not in AMFI_IDENTITY:
                continue
            ident = AMFI_IDENTITY[canonical_name]
            if ident["code"] not in seen_funds:
                funds.append({
                    "amc_slug": "ppfas",
                    "amfi_code": ident["code"],
                    "scheme_name": f"{canonical_name} - Direct Plan - Growth",
                    "isin_growth": ident["isin"],
                    "isin_reinvest": None,
                    "category": CATEGORY[canonical_name],
                    "asset_class": asset_class_for(bucket["holdings"]),
                    "plan_type": "direct-growth",
                })
                seen_funds.add(ident["code"])
            disclosures.append(build_disclosure(canonical_name, period, bucket))

    bundle = {"amcs": amcs, "funds": funds, "disclosures": disclosures}
    out_path = ROOT / "out" / "ppfas_bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2))
    print(f"{len(funds)} funds, {len(disclosures)} disclosures -> {out_path}")


if __name__ == "__main__":
    main()
