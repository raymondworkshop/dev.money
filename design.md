# dev.money - Project Design & Layout

## 1. Project Summary
`dev.money` is an automated financial analysis tool designed to identify undervalued stocks with high growth potential, mimicking Warren Buffett's investment philosophy. The system fetches financial reports (10-K/10-Q), extracts key metrics, and uses LLM-backed analysis to evaluate qualitative factors like "Moats" and management risks.

## 2. Investment Logic (from GEMINI.md)
*   **Operating Margin**: Analyze R&D spending vs. Revenue growth.
*   **Free Cash Flow (FCF)**: Adjusted for Capital Expenditure.
*   **Debt-to-Equity**: Monitor leverage and cash reserves.
*   **PEG Ratio**: Filter for stocks where PEG < 1 (Price/Earnings vs. Growth).
*   **Moat Analysis**: Evaluate Brand, Switching Costs, and Network Effects.
*   **Risk Detection**: Analyze MD&A and Financial Statement Notes for "hidden" issues.

## 3. Directory Layout
A flat structure is used for simplicity and ease of access.

```text
dev.money/
├── GEMINI.md              # Project requirements and investment philosophy
├── design.md              # This design and layout document
├── raw/                   # Local storage for downloaded financial reports (JSON/XBRL)
├── outputs/               # Generated analysis reports and scoring data (MD/JSON)
└── scripts/               # Consolidated source code and tests
    ├── ingestion.py       # Data fetching logic (SEC EDGAR API, IR sites)
    ├── parser.py          # Statement extraction and LLM text analysis
    ├── metrics.py         # Financial calculation logic (PEG, FCF, etc.)
    ├── evaluator.py       # Investment scoring and valuation filters
    ├── analyze.py         # Main CLI entry point (analyze <ticker>)
    ├── reporter.py        # Report formatting and output generation
    └── test_suite.py      # Integrated unit and integration tests
```

## 4. Component Architecture

### A. Core Modules
*   **ingestion.py**: Automates retrieval of filings and stores them in `raw/`.
*   **parser.py**: Maps XBRL/JSON fields to a unified data model; invokes LLMs for qualitative summaries.
*   **metrics.py**: Pure functions for financial ratio calculations.
*   **evaluator.py**: Applies the "Value + Growth" scoring model based on parsed data and metrics.

### B. Interface & Verification
*   **analyze.py**: The user interface. Orchestrates the flow from ingestion -> parsing -> analysis -> reporting.
*   **reporter.py**: Takes the evaluator's output and generates a readable Markdown report in `outputs/`.
*   **test_suite.py**: Contains all validation logic for both mathematical accuracy and pipeline integrity.
