"""CLI entry point: analyze <ticker>."""

from __future__ import annotations

import argparse

from analyze_lib import evaluate, fetch_financial_report, parse_report, read_raw_report, write_report
from analyze_lib import answer_question


def run(
    ticker: str,
    question: str | None = None,
    online: bool = False,
    company_domain: str | None = None,
    company_ir_url: str | None = None,
) -> str:
    raw_path = fetch_financial_report(
        ticker,
        online=online,
        company_domain=company_domain,
        company_ir_url=company_ir_url,
    )
    raw = read_raw_report(raw_path)
    if question:
        print(answer_question(raw, question))
    parsed = parse_report(raw)
    evaluation = evaluate(parsed)
    report_path = write_report(parsed, evaluation)
    return str(report_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a stock ticker for value and growth potential.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--question", help="Optional natural-language question about the report.", default=None)
    parser.add_argument("--online", dest="online", action="store_true", help="Enable online enrichment from SEC + company only.")
    parser.add_argument("--offline", dest="online", action="store_false", help="Disable online enrichment and use local data only.")
    parser.set_defaults(online=True)
    parser.add_argument("--company-domain", default=None, help="Official company domain for IR URL allowlist.")
    parser.add_argument("--company-ir-url", default=None, help="Optional company IR URL to probe and record.")
    args = parser.parse_args()
    report = run(
        args.ticker,
        args.question,
        online=args.online,
        company_domain=args.company_domain,
        company_ir_url=args.company_ir_url,
    )
    print(f"Report generated: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
