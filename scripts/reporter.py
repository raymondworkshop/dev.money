"""Markdown report generator for evaluation results."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from evaluator import Evaluation
from metrics import (
    debt_to_equity,
    free_cash_flow,
    operating_margin,
    peg_ratio,
    rd_intensity,
    revenue_growth,
)
from parser import ParsedReport


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

    # Build a reusable metric snapshot for broad Q&A fallback.
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
        history: List[Dict[str, Any]] = list(raw.get("financials_history", []))
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

    # Generic routing for broad question coverage.
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
