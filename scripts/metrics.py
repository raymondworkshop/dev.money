"""Financial metric calculations used by the evaluator."""

from __future__ import annotations


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
