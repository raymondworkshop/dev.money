"""Investment evaluator based on value + growth + quality + risk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from metrics import (
    cash_to_debt,
    debt_to_equity,
    free_cash_flow,
    operating_margin,
    peg_ratio,
    rd_intensity,
    revenue_growth,
)
from parser import ParsedReport


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
