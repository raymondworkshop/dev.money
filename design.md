# dev.business — Project Design & Layout

## Architecture: Thin Harness, Fat Skills

Push intelligence up into skills; push execution down into deterministic tooling.

- **Skills** (`.cursor/skills/`) — markdown procedures that encode judgment, process, and domain knowledge. The description field is the resolver; the model matches user intent to skill descriptions.
- **Harness** (`scripts/*.py`) — thin CLI that runs the LLM, loads context, validates strict JSON, renders markdown, and enforces file boundaries.
- **AGENTS.md** — system prompt and JSON contracts for sync, query, and audit harnesses.

Latent space is where intelligence lives; deterministic space is where trust lives. Anything inferred in latent space must be marked `[AI Synthesis]` in wiki content.

```text
raw evidence -> curated wiki memory -> reasoning outputs
```

## Project Summary

`dev.business` is an LLM-native business knowledge base. The primary workflow ingests news articles from `newswiki/raw`, distills them into a structured wiki at `newswiki/wiki`, answers questions with citations, audits wiki health, and publishes a Quartz static site.

A secondary workflow (`make analyze TICKER=...`) evaluates individual stocks using SEC filings and the investment lens in `AGENTS.md`.

## Directory Layout

```text
dev.business/
├── AGENTS.md                 # LLM wiki contract, JSON schemas, investment lens
├── design.md                 # This document
├── Makefile                  # sync, query, audit, analyze, publish, site
├── .env / .env.example       # LLM provider configuration
├── .cursor/skills/           # sync-wiki, query-wiki, audit-wiki
├── launchd/                  # macOS scheduled publish plist
├── logs/                     # sync.log, publish.log
├── newswiki/
│   ├── raw/                  # Inbox: unprocessed articles (+ archive/)
│   ├── wiki/                 # Curated knowledge base (topics, INDEX.md)
│   ├── outputs/              # Query and audit report snapshots
│   └── _resources/           # Article images (synced with raw)
├── site/                     # Quartz static site (content/, public/)
├── raw/                      # (created on demand) SEC filing cache for analyze
├── outputs/                  # (created on demand) Ticker analysis reports
└── scripts/                  # All Python harnesses and tests
```

Path overrides: `SOURCE`, `WIKI`, `ARCHIVE`, `OUTPUTS` via Makefile or CLI flags.

## Makefile Entry Points

| Target | Script | Purpose |
|--------|--------|---------|
| `make sync` | `sync_wiki.py` | raw → wiki |
| `make query QUESTION="..."` | `query_wiki.py` | wiki → cited answer |
| `make audit` | `audit_wiki.py` | wiki health report (read-only) |
| `make analyze TICKER=MSFT` | `analyze.py` | ticker value + growth report |
| `make publish` | `publish.sh` | sync + site build + Cloudflare deploy |
| `make site` | `prepare_quartz_content.py` + Quartz | build or serve static site |
| `make test` | `test_suite.py` | unit and pipeline tests |

## Scripts Layout

### Wiki harness (primary)

| Script | Role |
|--------|------|
| `sync_wiki.py` | Scan raw inbox, call LLM, validate proposal JSON, render wiki markdown, update indexes, archive provenance |
| `query_wiki.py` | Load wiki context, synthesize cited answer, save to `newswiki/outputs` |
| `audit_wiki.py` | Deterministic link/index checks + LLM quality report |
| `llm_provider.py` | Shared MLX / Gemini / OpenAI provider with JSON extraction and fallback |
| `zh_convert.py` | Chinese text normalization for sync |
| `prepare_quartz_content.py` | Copy and trim wiki content into `site/content/` |
| `publish.sh` | Wait for MLX, run sync, build and deploy site |

### Ticker analysis (secondary)

| Script | Role |
|--------|------|
| `analyze.py` | CLI: ingestion → parse → evaluate → report |
| `ingestion.py` | Fetch SEC EDGAR filings; store JSON in `raw/` |
| `parser.py` | Map filing fields to unified model; LLM qualitative summaries |
| `metrics.py` | Pure functions: PEG, FCF, operating margin, revenue growth |
| `evaluator.py` | Value + growth scoring from parsed data |
| `reporter.py` | Render Markdown report to `outputs/` |

### Verification

| Script | Role |
|--------|------|
| `test_suite.py` | Tests for wiki harness, LLM provider, site prep, and analyze pipeline |
| `fixtures/` | Sample raw markdown, proposal JSON, query/audit responses |

## Component Flows

### A. Sync (raw → wiki)

```text
newswiki/raw/*.md
  → sync_wiki.py (LLM proposes JSON via AGENTS.md)
  → validate + render
  → newswiki/wiki/<topic>/<article>.md
  → update INDEX.md, archive stub, delete inbox file
```

### B. Query (wiki → answer)

```text
newswiki/wiki + INDEX.md
  → query_wiki.py (LLM cites evidence)
  → newswiki/outputs/<slug>.md
```

### C. Publish (wiki → site)

```text
make publish
  → sync_wiki.py
  → prepare_quartz_content.py → site/content/
  → Quartz build → site/public/
  → wrangler pages deploy
```

### D. Analyze (ticker → report)

```text
make analyze TICKER=MSFT
  → ingestion.py → raw/<ticker>.json
  → parser.py → metrics.py → evaluator.py
  → reporter.py → outputs/<ticker>_analysis.md
```

## Investment Logic (analyze workflow)

From `AGENTS.md`:

- **Operating Margin**: margin quality, R&D intensity, revenue growth
- **Free Cash Flow**: operating cash flow minus capital expenditure
- **Debt-to-Equity**: leverage, cash reserves, refinancing risk
- **PEG Ratio**: growth at a reasonable price; PEG below 1 is attractive when quality holds
- **Moat Analysis**: brand, switching costs, network effects, scale, data, distribution
- **Risk Detection**: MD&A, notes, hidden liabilities, customer concentration, regulatory risk

## LLM Providers

Configured in `.env`. Default is local MLX (`LLM_PROVIDER=mlx`). Cloud options: `gemini`, `openai` (with MLX fallback on failure). Wiki harnesses load `AGENTS.md` as the system prompt.

## Skills

| Skill | Harness |
|-------|---------|
| `.cursor/skills/sync-wiki/` | `scripts/sync_wiki.py` |
| `.cursor/skills/query-wiki/` | `scripts/query_wiki.py` |
| `.cursor/skills/audit-wiki/` | `scripts/audit_wiki.py` |

Skills tell the model *how* to reason; scripts own *what* gets written to disk.
