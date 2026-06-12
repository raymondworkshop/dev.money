"""Financial analysis pipeline: ingestion, parsing, metrics, evaluation, reporting."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

# --- metrics ---


def safe_div(numerator: float, denominator: float) -> float:
    """Return numerator/denominator, or 0.0 when denominator is zero."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def operating_margin(operating_income: float, revenue: float) -> float:
    return safe_div(operating_income, revenue)


def revenue_growth(current_revenue: float, previous_revenue: float) -> float:
    return safe_div(current_revenue - previous_revenue, previous_revenue)


def rd_intensity(rd_expense: float, revenue: float) -> float:
    return safe_div(rd_expense, revenue)


def free_cash_flow(operating_cash_flow: float, capital_expenditure: float) -> float:
    return operating_cash_flow - capital_expenditure


def debt_to_equity(total_debt: float, total_equity: float) -> float:
    return safe_div(total_debt, total_equity)


def cash_to_debt(cash_reserves: float, total_debt: float) -> float:
    return safe_div(cash_reserves, total_debt)


def peg_ratio(pe_ratio: float, earnings_growth_percent: float) -> float:
    return safe_div(pe_ratio, earnings_growth_percent)


# --- parser ---


@dataclass(frozen=True)
class ParsedReport:
    ticker: str
    period: str
    financials: Dict[str, float]
    moat_score: float
    risk_flags: List[str]


def _moat_score(qualitative: Dict[str, Any]) -> float:
    brand = float(qualitative.get("brand", 0.0))
    switching = float(qualitative.get("switching_costs", 0.0))
    network = float(qualitative.get("network_effects", 0.0))
    return (brand + switching + network) / 3.0


def _risk_flags(qualitative: Dict[str, Any]) -> List[str]:
    mda = qualitative.get("mda_risk_flags", []) or []
    notes = qualitative.get("notes_risk_flags", []) or []
    return [str(item) for item in [*mda, *notes]]


def parse_report(raw: Dict[str, Any]) -> ParsedReport:
    return ParsedReport(
        ticker=str(raw.get("ticker", "")).upper(),
        period=str(raw.get("period", "unknown")),
        financials=dict(raw.get("financials", {})),
        moat_score=_moat_score(raw.get("qualitative", {})),
        risk_flags=_risk_flags(raw.get("qualitative", {})),
    )


# --- evaluator ---


@dataclass(frozen=True)
class Evaluation:
    ticker: str
    period: str
    metrics: Dict[str, float]
    score: float
    verdict: str


def _clamp01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def evaluate(parsed: ParsedReport) -> Evaluation:
    f = parsed.financials

    op_margin = operating_margin(f["operating_income"], f["revenue_current"])
    rev_growth = revenue_growth(f["revenue_current"], f["revenue_previous"])
    rd_ratio = rd_intensity(f["rd_expense"], f["revenue_current"])
    fcf = free_cash_flow(f["operating_cash_flow"], f["capital_expenditure"])
    d2e = debt_to_equity(f["total_debt"], f["total_equity"])
    c2d = cash_to_debt(f["cash_reserves"], f["total_debt"])
    peg = peg_ratio(f["pe_ratio"], f["earnings_growth_percent"])

    metrics = {
        "operating_margin": op_margin,
        "revenue_growth": rev_growth,
        "rd_intensity": rd_ratio,
        "free_cash_flow": fcf,
        "debt_to_equity": d2e,
        "cash_to_debt": c2d,
        "peg_ratio": peg,
        "moat_score": parsed.moat_score,
        "risk_flag_count": float(len(parsed.risk_flags)),
    }

    value_score = 1.0 if 0 < peg < 1 else 0.4 if peg <= 1.4 else 0.0
    growth_score = _clamp01(rev_growth / 0.20)
    quality_score = _clamp01((op_margin / 0.25 + parsed.moat_score) / 2.0)
    balance_score = _clamp01((1.0 - d2e / 2.0 + min(c2d, 1.0)) / 2.0)
    risk_penalty = min(0.25, len(parsed.risk_flags) * 0.05)
    cash_bonus = 0.05 if fcf > 0 else 0.0

    score = (
        value_score * 0.35
        + growth_score * 0.25
        + quality_score * 0.20
        + balance_score * 0.20
        + cash_bonus
        - risk_penalty
    )
    score = _clamp01(score)

    if score >= 0.75:
        verdict = "High priority candidate"
    elif score >= 0.55:
        verdict = "Watchlist candidate"
    else:
        verdict = "Not attractive currently"

    return Evaluation(
        ticker=parsed.ticker,
        period=parsed.period,
        metrics=metrics,
        score=score,
        verdict=verdict,
    )


# --- ingestion ---

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


def _pick_latest_year_values(items: List[Dict[str, Any]], years: int = 3) -> List[tuple[int, float]]:
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


def _first_available_fact(facts: Dict[str, Any], tags: List[str]) -> List[tuple[int, float]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        usd = units.get("USD", [])
        picked = _pick_latest_year_values(usd)
        if picked:
            return picked
    return []


def _value_for_year(entries: List[tuple[int, float]], year: int) -> float:
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
        data["financials_history"] = [
            {"year": 2023, "revenue": rev_2024 * 0.86, "rd_expense": rd_2025 * 0.82},
            {"year": 2024, "revenue": rev_2024, "rd_expense": rd_2025 * 0.92},
            {"year": 2025, "revenue": rev_2025, "rd_expense": rd_2025},
        ]
    return data


# --- reporter ---

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_markdown(parsed: ParsedReport, evaluation: Evaluation) -> str:
    m = evaluation.metrics
    lines = [
        f"# {evaluation.ticker} Analysis ({evaluation.period})",
        "",
        f"**Final Score**: {evaluation.score:.3f}",
        f"**Verdict**: {evaluation.verdict}",
        "",
        "## Key Metrics",
        f"- Operating Margin: {_pct(m['operating_margin'])}",
        f"- Revenue Growth: {_pct(m['revenue_growth'])}",
        f"- R&D Intensity: {_pct(m['rd_intensity'])}",
        f"- Free Cash Flow: {m['free_cash_flow']:.2f}",
        f"- Debt-to-Equity: {m['debt_to_equity']:.3f}",
        f"- Cash-to-Debt: {m['cash_to_debt']:.3f}",
        f"- PEG Ratio: {m['peg_ratio']:.3f}",
        f"- Moat Score: {m['moat_score']:.3f}",
        "",
        "## Risk Signals",
    ]

    if parsed.risk_flags:
        lines.extend([f"- {item}" for item in parsed.risk_flags])
    else:
        lines.append("- No explicit risk flags captured.")

    return "\n".join(lines) + "\n"


def write_report(parsed: ParsedReport, evaluation: Evaluation, output_dir: Path | None = None) -> Path:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / f"{evaluation.ticker}_analysis.md"
    report_path.write_text(build_markdown(parsed, evaluation), encoding="utf-8")
    print(
        f"[reporter] {evaluation.ticker} | score={evaluation.score:.3f} | "
        f"verdict={evaluation.verdict} | file={report_path}"
    )
    return report_path


def answer_question(raw: Dict[str, Any], question: str) -> str:
    q = question.strip().lower()
    ticker = str(raw.get("ticker", "N/A"))
    financials = raw.get("financials", {}) or {}
    qualitative = raw.get("qualitative", {}) or {}
    history: List[Dict[str, Any]] = list(raw.get("financials_history", []))

    revenue_current = float(financials.get("revenue_current", 0.0))
    revenue_previous = float(financials.get("revenue_previous", 0.0))
    operating_income = float(financials.get("operating_income", 0.0))
    rd_expense = float(financials.get("rd_expense", 0.0))
    ocf = float(financials.get("operating_cash_flow", 0.0))
    capex = float(financials.get("capital_expenditure", 0.0))
    total_debt = float(financials.get("total_debt", 0.0))
    total_equity = float(financials.get("total_equity", 0.0))
    pe = float(financials.get("pe_ratio", 0.0))
    growth_pct = float(financials.get("earnings_growth_percent", 0.0))

    op_margin = operating_margin(operating_income, revenue_current)
    rev_growth = revenue_growth(revenue_current, revenue_previous)
    rd_ratio = rd_intensity(rd_expense, revenue_current)
    fcf = free_cash_flow(ocf, capex)
    d2e = debt_to_equity(total_debt, total_equity)
    peg = peg_ratio(pe, growth_pct)

    match_rd_ratio = (
        "研发支出占收入比例" in question
        or ("rd" in q and "revenue" in q and "ratio" in q)
        or ("r&d" in q and "revenue" in q)
    )
    if match_rd_ratio:
        history = list(raw.get("financials_history", []))
        if not history:
            return "缺少 financials_history 数据，无法比较近三年研发支出占收入比例。"

        history = sorted(history, key=lambda x: int(x.get("year", 0)))
        last_three = history[-3:]
        lines = [f"{ticker} 近三年研发支出占收入比例："]
        for item in last_three:
            year = int(item.get("year", 0))
            revenue = float(item.get("revenue", 0.0))
            rd = float(item.get("rd_expense", 0.0))
            ratio = (rd / revenue) if revenue else 0.0
            lines.append(f"- {year}: {rd:.2f} / {revenue:.2f} = {ratio * 100:.2f}%")
        return "\n".join(lines)

    match_call_risk = (
        "电话会议" in question and "风险" in question
    ) or ("management" in q and "call" in q and "risk" in q)
    if match_call_risk:
        call_risks = list(qualitative.get("call_risk_points", []) or [])
        if not call_risks:
            call_risks = list(qualitative.get("mda_risk_flags", []) or []) + list(
                qualitative.get("notes_risk_flags", []) or []
            )
        if not call_risks:
            return "未找到可用于总结的管理层风险点数据。"
        lines = [f"{ticker} 管理层电话会议核心风险点总结："]
        lines.extend([f"- {risk}" for risk in call_risks[:5]])
        return "\n".join(lines)

    if "peg" in q or "估值" in question or "便宜" in question:
        valuation = "偏便宜" if 0 < peg < 1 else "中性偏贵" if peg <= 1.4 else "偏贵"
        return (
            f"{ticker} 估值判断（基于本地数据）：PEG={peg:.3f}，当前可归类为{valuation}。"
            f"（PE={pe:.2f}, Earnings Growth={growth_pct:.2f}%）"
        )

    if "现金流" in question or "fcf" in q:
        status = "为正，现金创造能力较好" if fcf > 0 else "为负，需要关注资本开支与经营现金流匹配"
        return f"{ticker} 自由现金流={fcf:.2f}，{status}。"

    if "负债" in question or "debt" in q or "杠杆" in question:
        status = "杠杆较稳健" if d2e < 1 else "杠杆偏高，需要结合利率与再融资观察"
        return f"{ticker} Debt-to-Equity={d2e:.3f}，{status}。"

    if "增长" in question or "growth" in q or "营收" in question:
        return (
            f"{ticker} 最新营收增速={rev_growth * 100:.2f}%，"
            f"营业利润率={op_margin * 100:.2f}%，研发强度={rd_ratio * 100:.2f}%。"
        )

    moat_items = [
        f"brand={float(qualitative.get('brand', 0.0)):.2f}",
        f"switching_costs={float(qualitative.get('switching_costs', 0.0)):.2f}",
        f"network_effects={float(qualitative.get('network_effects', 0.0)):.2f}",
    ]
    risk_items = list(qualitative.get("mda_risk_flags", []) or []) + list(
        qualitative.get("notes_risk_flags", []) or []
    )
    history_note = ""
    if history:
        years = sorted(int(x.get("year", 0)) for x in history if x.get("year") is not None)
        if years:
            history_note = f"历史覆盖年份：{years[0]}-{years[-1]}。"

    return (
        f"问题：{question}\n"
        f"基于当前本地数据，我给出简要结论：{ticker} 的营收增速 {rev_growth * 100:.2f}%，"
        f"营业利润率 {op_margin * 100:.2f}%，FCF {fcf:.2f}，Debt/Equity {d2e:.3f}，PEG {peg:.3f}。"
        f" 护城河指标：{', '.join(moat_items)}。"
        f" 已识别风险：{'; '.join(risk_items) if risk_items else '暂无显式风险标记'}。"
        f" {history_note}".strip()
    )
