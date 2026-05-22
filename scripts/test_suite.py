"""Integrated unit + pipeline tests for dev.money scripts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluator import evaluate
from ingestion import fetch_financial_report, read_raw_report
from metrics import free_cash_flow, operating_margin, peg_ratio, revenue_growth
from parser import parse_report
from reporter import build_markdown, write_report


class MetricsTests(unittest.TestCase):
    def test_operating_margin(self) -> None:
        self.assertAlmostEqual(operating_margin(25, 100), 0.25)

    def test_revenue_growth(self) -> None:
        self.assertAlmostEqual(revenue_growth(120, 100), 0.2)

    def test_free_cash_flow(self) -> None:
        self.assertEqual(free_cash_flow(42, 10), 32)

    def test_peg_ratio(self) -> None:
        self.assertAlmostEqual(peg_ratio(18, 24), 0.75)


class PipelineTests(unittest.TestCase):
    def test_end_to_end_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_dir = tmp_path / "raw"
            out_dir = tmp_path / "outputs"

            raw_path = fetch_financial_report("AAPL", raw_dir=raw_dir)
            raw = read_raw_report(raw_path)
            parsed = parse_report(raw)
            evaluation = evaluate(parsed)
            md = build_markdown(parsed, evaluation)
            report_path = write_report(parsed, evaluation, output_dir=out_dir)

            self.assertIn("AAPL", md)
            self.assertTrue(0.0 <= evaluation.score <= 1.0)
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
