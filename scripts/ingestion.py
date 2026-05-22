"""Data ingestion for local-first SEC/IR report fixtures."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple


RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ALLOWED_DOMAINS = {"sec.gov", "www.sec.gov", "data.sec.gov"}


def _is_allowed_domain(url: str, allowed_domains: set[str]) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == d or host.endswith(f".{d}") for d in allowed_domains)


def _fetch_json(url: str) -> Dict[str, Any]:
    if not _is_allowed_domain(url, SEC_ALLOWED_DOMAINS):
        raise ValueError(f"Blocked non-SEC URL: {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "dev.money/0.1 (contact: local-user@example.com)"},
    )
    # Keep TLS behavior explicit to avoid machine-level surprises.
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ticker_to_cik(ticker: str) -> str:
    payload = _fetch_json(SEC_TICKERS_URL)
    needle = ticker.upper()
    for _, item in payload.items():
        if str(item.get("ticker", "")).upper() == needle:
            return str(int(item["cik_str"])).zfill(10)
    raise ValueError(f"Ticker not found in SEC mapping: {ticker}")


def _pick_latest_year_values(items: List[Dict[str, Any]], years: int = 3) -> List[Tuple[int, float]]:
    annual: Dict[int, float] = {}
    for row in items:
        fy = row.get("fy")
        fp = row.get("fp")
        val = row.get("val")
        form = str(row.get("form", ""))
        if fy is None or val is None:
            continue
        if fp != "FY":
            continue
        if form not in {"10-K", "10-K/A", "20-F", "40-F"}:
            continue
        year = int(fy)
        annual[year] = float(val)
    return sorted(annual.items())[-years:]


def _first_available_fact(facts: Dict[str, Any], tags: List[str]) -> List[Tuple[int, float]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        usd = units.get("USD", [])
        picked = _pick_latest_year_values(usd)
        if picked:
            return picked
    return []


def _value_for_year(entries: List[Tuple[int, float]], year: int) -> float:
    for y, v in entries:
        if y == year:
            return v
    return 0.0


def _ensure_company_url_allowed(company_url: str, company_domain: str) -> str:
    parsed = urllib.parse.urlparse(company_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Company IR URL must use http/https.")
    host = parsed.netloc.lower()
    base = company_domain.lower()
    if not (host == base or host.endswith(f".{base}")):
        raise ValueError(f"Blocked non-company URL: {company_url}")
    return company_url


def _probe_company_url(company_url: str) -> bool:
    req = urllib.request.Request(
        company_url,
        method="HEAD",
        headers={"User-Agent": "dev.money/0.1 (contact: local-user@example.com)"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context, timeout=20) as resp:
        return int(resp.status) < 400


def _fetch_online_snapshot(ticker: str) -> Dict[str, Any]:
    cik = _ticker_to_cik(ticker)
    facts = _fetch_json(SEC_COMPANYFACTS_URL.format(cik=cik))

    revenues = _first_available_fact(
        facts,
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    )
    rd = _first_available_fact(facts, ["ResearchAndDevelopmentExpense"])
    op_income = _first_available_fact(facts, ["OperatingIncomeLoss"])
    ocf = _first_available_fact(facts, ["NetCashProvidedByUsedInOperatingActivities"])
    capex = _first_available_fact(facts, ["PaymentsToAcquirePropertyPlantAndEquipment"])
    debt = _first_available_fact(
        facts,
        ["LongTermDebtAndFinanceLeaseLiabilities", "LongTermDebtNoncurrent", "DebtCurrent"],
    )
    equity = _first_available_fact(facts, ["StockholdersEquity"])
    cash = _first_available_fact(facts, ["CashAndCashEquivalentsAtCarryingValue"])

    years = sorted({y for y, _ in revenues})[-3:]
    if len(years) < 2:
        raise ValueError("SEC data has insufficient annual revenue history.")

    y_prev, y_cur = years[-2], years[-1]
    history = [
        {
            "year": y,
            "revenue": _value_for_year(revenues, y),
            "rd_expense": _value_for_year(rd, y),
        }
        for y in years
    ]
    return {
        "ticker": ticker.upper(),
        "period": f"FY-{y_cur}",
        "financials": {
            "revenue_current": _value_for_year(revenues, y_cur),
            "revenue_previous": _value_for_year(revenues, y_prev),
            "operating_income": _value_for_year(op_income, y_cur),
            "rd_expense": _value_for_year(rd, y_cur),
            "operating_cash_flow": _value_for_year(ocf, y_cur),
            "capital_expenditure": abs(_value_for_year(capex, y_cur)),
            "total_debt": _value_for_year(debt, y_cur),
            "total_equity": _value_for_year(equity, y_cur),
            "cash_reserves": _value_for_year(cash, y_cur),
            # Market pricing fields are not present in SEC companyfacts.
            "pe_ratio": 0.0,
            "earnings_growth_percent": 0.0,
        },
        "financials_history": history,
        "qualitative": {
            "brand": 0.0,
            "switching_costs": 0.0,
            "network_effects": 0.0,
            "call_risk_points": [],
            "mda_risk_flags": [],
            "notes_risk_flags": [],
        },
        "sources": [
            {"type": "sec_company_tickers", "url": SEC_TICKERS_URL},
            {"type": "sec_companyfacts", "url": SEC_COMPANYFACTS_URL.format(cik=cik)},
        ],
    }


def _default_fixture(ticker: str) -> Dict[str, Any]:
    """Deterministic fallback so the pipeline runs without network access."""
    return {
        "ticker": ticker.upper(),
        "period": "FY-2025",
        "financials": {
            "revenue_current": 150_000_000.0,
            "revenue_previous": 120_000_000.0,
            "operating_income": 33_000_000.0,
            "rd_expense": 12_000_000.0,
            "operating_cash_flow": 42_000_000.0,
            "capital_expenditure": 10_000_000.0,
            "total_debt": 35_000_000.0,
            "total_equity": 70_000_000.0,
            "cash_reserves": 22_000_000.0,
            "pe_ratio": 18.0,
            "earnings_growth_percent": 26.0,
        },
        "qualitative": {
            "brand": 0.75,
            "switching_costs": 0.68,
            "network_effects": 0.72,
            "call_risk_points": [
                "AI infrastructure capex pressure may compress near-term margins.",
                "Enterprise customer budget cycles remain uneven across regions.",
                "Regulatory and compliance changes may slow product rollout in some markets.",
            ],
            "mda_risk_flags": ["cyclical demand in one segment"],
            "notes_risk_flags": ["single pending legal matter disclosed"],
        },
    }


def fetch_financial_report(
    ticker: str,
    raw_dir: Path | None = None,
    online: bool = False,
    company_domain: str | None = None,
    company_ir_url: str | None = None,
) -> Path:
    """
    Load or create local raw report for ticker and return file path.

    By default it is offline-first.
    If online=True, enrich from SEC only, plus optional company IR URL probe.
    """
    target_dir = raw_dir or RAW_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{ticker.upper()}.json"
    data: Dict[str, Any]
    if file_path.exists():
        data = json.loads(file_path.read_text(encoding="utf-8"))
    else:
        data = _default_fixture(ticker)

    if online:
        try:
            online_data = _fetch_online_snapshot(ticker)
            if company_ir_url:
                if not company_domain:
                    raise ValueError("--company-domain is required when --company-ir-url is provided.")
                checked_url = _ensure_company_url_allowed(company_ir_url, company_domain)
                reachable = _probe_company_url(checked_url)
                online_data.setdefault("sources", []).append(
                    {"type": "company_ir", "url": checked_url, "reachable": reachable}
                )
            data = online_data
            print(f"[ingestion] online enrichment complete for {ticker.upper()} (SEC + company only)")
        except (ValueError, urllib.error.URLError, TimeoutError) as err:
            print(f"[ingestion] online enrichment failed for {ticker.upper()}: {err}. fallback=local")

    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path


def read_raw_report(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "financials_history" not in data:
        f = data.get("financials", {})
        rev_2025 = float(f.get("revenue_current", 0.0))
        rev_2024 = float(f.get("revenue_previous", 0.0))
        rd_2025 = float(f.get("rd_expense", 0.0))
        # Deterministic fallback history based on current/previous snapshot.
        data["financials_history"] = [
            {"year": 2023, "revenue": rev_2024 * 0.86, "rd_expense": rd_2025 * 0.82},
            {"year": 2024, "revenue": rev_2024, "rd_expense": rd_2025 * 0.92},
            {"year": 2025, "revenue": rev_2025, "rd_expense": rd_2025},
        ]
    return data
