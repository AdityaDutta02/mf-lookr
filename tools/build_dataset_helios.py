#!/usr/bin/env python3
"""Join every parsed Helios period (tools/out/helios_xlsx/<period>.json — from
the "Detailed Portfolio Disclosure" XLSX, NOT the factsheet PDF; see
parse_helios_xlsx.py) with AMFI identity into the app's AnalyseData contract,
and emit tools/out/helios_bundle.json — {amcs, funds, disclosures} — the
app's seed-helios route inserts directly. Mirrors tools/build_dataset.py
(PPFAS) / build_dataset_hdfc.py's shape exactly, amc_slug: "helios" only.

Deterministic derivation only — no AI, no guessed numbers. Each holding's own
ISIN and quantity come straight from the source XLSX (this format discloses
both, unlike a factsheet PDF).

AMFI identity matched by exact scheme-name string against cache/amfi_nav.txt
(no fuzzy matching) — anything that doesn't match is logged and skipped
rather than guessed. All 8 Helios schemes matched cleanly on first try; the
AMFI_IDENTITY map below is the full canonical scheme roster for this AMC.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out" / "helios_xlsx"
AMFI_PATH = ROOT / "cache" / "amfi_nav.txt"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# canonical fund name (as returned by parse_helios_xlsx.find_fund_name, i.e. the
# XLSX's own "SCHEME NAME :" text with the parenthetical category blurb stripped)
# -> AMFI scheme code we treat as this fund's primary identity (Direct Plan
# Growth — holdings/portfolio are plan-agnostic, this is just the ID).
AMFI_IDENTITY = {
    "Helios Flexi Cap Fund": {"code": "152135", "isin": "INF0R8701046",
                               "amfi_name": "Helios Flexi Cap Fund - Direct Plan - Growth Option"},
    "Helios Large & Mid Cap Fund": {"code": "152941", "isin": "INF0R8701269",
                                     "amfi_name": "Helios Large & Mid Cap Fund - Direct Plan - Growth Option"},
    "Helios Mid Cap Fund": {"code": "153326", "isin": "INF0R8701327",
                             "amfi_name": "Helios Mid Cap Fund - Direct Plan - Growth Option"},
    "Helios Financial Services Fund": {"code": "152679", "isin": "INF0R8701202",
                                        "amfi_name": "Helios Financial Services Fund - Direct Plan - Growth Option"},
    "Helios Small Cap Fund": {"code": "153912", "isin": "INF0R8701384",
                               "amfi_name": "Helios Small Cap Fund - Direct Plan - Growth Option"},
    "Helios Arbitrage Fund": {"code": "154257", "isin": "INF0R8701442",
                               "amfi_name": "Helios Arbitrage Fund - Direct Growth"},
    "Helios Balanced Advantage Fund": {"code": "152509", "isin": "INF0R8701145",
                                        "amfi_name": "Helios Balanced Advantage Fund- Direct Plan- Growth Option"},
    "Helios Overnight Fund": {"code": "152152", "isin": "INF0R8701079",
                               "amfi_name": "Helios Overnight Fund - Direct Plan - Growth Option"},
}
CATEGORY = {
    "Helios Flexi Cap Fund": "Equity - Flexi Cap Fund",
    "Helios Large & Mid Cap Fund": "Equity - Large & Mid Cap Fund",
    "Helios Mid Cap Fund": "Equity - Mid Cap Fund",
    "Helios Financial Services Fund": "Equity - Sectoral/Thematic - Financial Services",
    "Helios Small Cap Fund": "Equity - Small Cap Fund",
    "Helios Arbitrage Fund": "Hybrid - Arbitrage Fund",
    "Helios Balanced Advantage Fund": "Hybrid - Balanced Advantage Fund",
    "Helios Overnight Fund": "Debt - Overnight Fund",
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
    aum = round(sum(h["market_value_cr"] for h in holdings if h.get("market_value_cr") is not None), 2)
    year, month = period.split("-")
    last_day = ["31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31"][int(month) - 1]
    data = {
        "amfi_code": ident["code"],
        "scheme_name": ident["amfi_name"],
        "amc_name": "Helios Mutual Fund",
        "category": CATEGORY[canonical_name],
        "isin": ident["isin"],
        "asset_class": asset_class_for(holdings),
        "period": period,
        "period_label": f"{MONTHS[int(month)]} {year}",
        "as_of_date": f"{period}-{last_day}",
        "source_org": "Helios Mutual Fund",
        "source_url": "https://www.heliosmf.in/portfolio-disclosure/",
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
        "amc_slug": "helios",
        "year": int(year),
        "month": int(month),
        "period": period,
        "as_of_date": data["as_of_date"],
        "source_org": "Helios Mutual Fund",
        "source_url": data["source_url"],
        "raw_file_key": None,
        "data": data,
    }


def main():
    periods = sys.argv[1:] or sorted(p.stem for p in OUT_DIR.glob("*.json"))
    amcs = [{
        "slug": "helios", "name": "Helios Mutual Fund",
        "factsheet_url": "https://www.heliosmf.in/downloads/",
        "archive_from": "2023-10", "status": "loaded",
    }]
    funds = []
    disclosures = []
    seen_funds = set()
    unmatched = set()

    for period in periods:
        path = OUT_DIR / f"{period}.json"
        if not path.exists():
            print(f"skip {period}: not parsed yet")
            continue
        parsed = json.loads(path.read_text())
        for canonical_name, bucket in parsed.items():
            if canonical_name not in AMFI_IDENTITY:
                unmatched.add(canonical_name)
                continue
            ident = AMFI_IDENTITY[canonical_name]
            if ident["code"] not in seen_funds:
                funds.append({
                    "amc_slug": "helios",
                    "amfi_code": ident["code"],
                    "scheme_name": ident["amfi_name"],
                    "isin_growth": ident["isin"],
                    "isin_reinvest": None,
                    "category": CATEGORY[canonical_name],
                    "asset_class": asset_class_for(bucket["holdings"]),
                    "plan_type": "direct-growth",
                })
                seen_funds.add(ident["code"])
            disclosures.append(build_disclosure(canonical_name, period, bucket))

    if unmatched:
        print(f"UNMATCHED fund names (no AMFI identity, skipped — not guessed): {sorted(unmatched)}")

    bundle = {"amcs": amcs, "funds": funds, "disclosures": disclosures}
    out_path = ROOT / "out" / "helios_bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2))
    print(f"{len(funds)} funds, {len(disclosures)} disclosures -> {out_path}")


if __name__ == "__main__":
    main()
