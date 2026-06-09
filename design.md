# dev.news - Project Design & Layout

## the architecture philosophy - Thin Harness, Fat Skills  
* Push intelligence up into skills, and push execution down into deterministic tooling. keep the harness thin.  
    - Fast skills sit on top
        + markdown procedures that **encode judgement, process, and domain knowledge** 
    - thin cli harness sits in the middle.
        + JSON in, text out. Read-only by default.
    - deterministic is where trust lives. 
        + Same input, same output. Every time. SQL queris. Compiled code. ARITHMETIC.

* a skill file tell the model how
    - works like a method call 

* the harness is the program that runs the LLM  
    - runs the model in a loop,
    reads and writes your files, manages context, and enforces safety.

* Resolvers tell it what to load and when  
    - The description is the resolver.
    Every skill has a description field, and the model matches user intent to skill descriptions automatically.

* latent space vs deterministic space  
    - latent spcae is where intelligence lives
    - deterministic is where trust lives  

* Diarization is the step that makes AI useful for real knowledge work

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
