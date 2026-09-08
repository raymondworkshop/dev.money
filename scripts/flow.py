"""CLI: institutional price/volume flow (accumulation vs distribution)."""

from __future__ import annotations

import argparse
from pathlib import Path

from flow_lib import judgment_rules, run_flow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Estimate accumulation/distribution from daily price and volume."
    )
    parser.add_argument("ticker", help="Ticker or ETF symbol, e.g. AAPL or SPY")
    parser.add_argument(
        "--range",
        default="1y",
        help="Yahoo chart range (default: 1y). Examples: 6mo, 1y, 2y",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Report directory (default: repo outputs/)",
    )
    args = parser.parse_args()
    path, report = run_flow(args.ticker, range_=args.range, output_dir=args.output_dir)

    print(f"{report.ticker} 结论: {report.signal}")
    print()
    print("理由:")
    for reason in report.reasons:
        print(f"  - {reason}")
    print()
    print("怎么判断的:")
    for rule in judgment_rules():
        print(f"  - {rule}")
    print()
    print(f"报告: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
