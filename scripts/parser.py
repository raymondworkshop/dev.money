"""Parser that maps raw filing payloads into a normalized analysis model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


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
