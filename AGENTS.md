# dev.news-wiki LLM Wiki Contract

## Purpose

The wiki is the context window. Scripts are the executor. Raw files are provenance.

This repository turns useful news articles into an LLM-native knowledge base:

```text
raw evidence -> curated wiki memory -> reasoning outputs
```

Every generated page should help future agents retrieve context, reason from evidence, and emit machine-checkable JSON.

## Core Principle: Thin Harness, Fat Skills

- **Skills/GEMINI.md** encode judgment, process, and domain knowledge.
- **Scripts** load files, validate JSON, render markdown, update indexes, archive files, and save outputs.
- **LLM output to scripts must be strict JSON**. Do not explain file operations outside JSON fields.
- **Deterministic space is where trust lives**. Anything inferred in latent space must be marked.

## Roles

- **Financial Analyst**: evaluate value + growth, moats, cash flow, leverage, and risk.
- **Librarian**: keep the wiki compact, linked, and source-grounded.
- **Operator**: respect harness boundaries; do not mutate files by hand when a script owns the operation.

## Path Configuration

Default layout:

- Source: `newswiki/raw`
- Archive: `<source>/archive`
- Wiki: `newswiki/wiki`
- Outputs: `newswiki/outputs`

All sync/query/audit harnesses accept path overrides through Makefile variables or CLI flags.

## Evidence Hierarchy

- **Raw**: original evidence and provenance. Usually private; do not treat as curated knowledge.
- **Wiki**: distilled memory. Primary layer for query and audit reasoning.
- **Outputs**: reasoning snapshots such as query answers, audits, and analysis reports.
- **External URLs**: original publication links from front matter.

Clickable links are semantic edges for humans and retrieval:

- Wiki link: `[[topic/article-slug|Title]]`
- Raw link: `[[../raw/archive/file.md|original source]]`
- Repo-root path: use in JSON fields such as `path`.

## Global Rules

- Preserve source/user language unless asked to translate.
- Never invent facts, figures, dates, companies, quotes, or sources.
- Use concise bullets; every sentence should earn context-window space.
- Use `[[wiki links]]` for companies, people, sectors, technologies, and topics.
- Separate fact from interpretation. Any unstated inference, causal explanation, or cross-article pattern must start with `[AI Synthesis]`.
- Cite wiki first, raw for verification, external URLs when useful.
- Do not manually duplicate harness behavior.

## Investment Lens

Use these when interpreting news wiki material:

- **Operating Margin**: margin quality, R&D intensity, revenue growth.
- **Free Cash Flow**: operating cash flow minus capital expenditure.
- **Debt-to-Equity**: leverage, cash reserves, refinancing risk.
- **PEG Ratio**: growth at a reasonable price; PEG below 1 is attractive when quality holds.
- **Moat Analysis**: brand, switching costs, network effects, scale, data, distribution.
- **Risk Detection**: MD&A, notes, hidden liabilities, customer concentration, aggressive recognition, regulatory/financing risk.

## Workflows

### sync-wiki: raw -> wiki

**Intent**: transform source markdown into curated wiki memory.

**Use**: `scripts/sync_wiki.py` or the `sync-wiki` skill.

**LLM does**

- Map source to an existing topic, or propose a new topic with rationale.
- Distill source-grounded sections and `key_takeaways`.
- Preserve front matter metadata when present.
- Add useful semantic `[[wiki links]]`.

**Harness does**

- Scan source files.
- Validate proposal JSON.
- Render wiki markdown.
- Update topic/root indexes.
- Archive processed sources.
- Maintain `<archive>/.sync_cache.json`.

**Output JSON**

```json
{
  "action": "create_article",
  "source_file": "<source-prefix>/file.md",
  "topic": {
    "slug": "topic-slug",
    "title": "Topic Title",
    "path": "<wiki-prefix>/topic-slug",
    "is_new": false,
    "rationale": "Why this topic fits."
  },
  "article": {
    "slug": "article-slug",
    "path": "<wiki-prefix>/topic-slug/article-slug.md",
    "title": "Source-language title",
    "front_matter": {
      "title": "Source-language title",
      "source": "https://example.com",
      "author": ["[[Author Name]]"],
      "published": "YYYY-MM-DD",
      "created": "YYYY-MM-DD",
      "description": "Source-language description"
    },
    "sections": [
      {
        "heading": "核心观点",
        "bullets": ["Source-grounded bullet.", "[AI Synthesis] Labeled inference."]
      }
    ],
    "key_takeaways": ["Concise takeaway."],
    "topic_footer": {
      "topic_link": "[[topic-slug/_index|Topic Title]]",
      "tags": ["#topic-slug"]
    }
  },
  "index_updates": {
    "topic_index_entry": "- [[article-slug|Title]] (YYYY-MM-DD) - Summary",
    "root_recent_entry": "- [[topic-slug/article-slug|Title]] (YYYY-MM-DD)"
  },
  "archive": {
    "should_archive": true,
    "status_row": "| file.md | Topic Title | `<wiki-prefix>/topic-slug/article-slug.md` | Archived |"
  },
  "review_notes": []
}
```

Allowed `action`: `create_article`, `skip_duplicate`, `needs_review`.
For Chinese articles use `核心观点`; for English articles use `Core View`.

### query-wiki: wiki -> answer

**Intent**: answer questions from curated wiki memory with clickable evidence.

**Use**: `scripts/query_wiki.py` or the `query-wiki` skill.

**LLM does**

- Interpret the question.
- Select relevant wiki evidence.
- Synthesize a concise answer.
- Add raw/external provenance when useful.
- Identify risks, gaps, and unknowns.

**Harness does**

- Load `INDEX.md` and topic `_index.md` context.
- Validate query JSON.
- Render markdown.
- Save to `<outputs>` when requested.

**Output JSON**

```json
{
  "question": "User question",
  "answer": {
    "summary": "One-paragraph answer.",
    "sections": [
      {
        "heading": "Answer Section",
        "bullets": ["Wiki-grounded point.", "[AI Synthesis] Labeled inference."]
      }
    ]
  },
  "citations": [
    {
      "type": "wiki",
      "path": "<wiki-prefix>/topic/article.md",
      "link": "[[topic/article|Title]]",
      "note": "Why this supports the answer."
    }
  ],
  "output": {
    "should_save": true,
    "filename_slug": "query-result"
  },
  "review_notes": []
}
```

Allowed citation `type`: `wiki`, `raw`, `external`. For `external`, use `url` instead of `path`/`link`.

### audit-wiki: wiki -> quality report

**Intent**: inspect wiki health without changing source or wiki files.

**Use**: `scripts/audit_wiki.py` or the `audit-wiki` skill.

**LLM does**

- Review deterministic findings from the harness.
- Prioritize quality issues.
- Flag missing links, thin coverage, unsupported claims, stale data, and weak synthesis.
- Recommend fixes without modifying files.

**Harness does**

- Scan wiki markdown for `[[links]]`.
- Resolve link targets.
- Detect broken links and index gaps.
- Build file inventory.
- Validate audit JSON.
- Render/save report.

**Output JSON**

```json
{
  "summary": "One-paragraph wiki health overview.",
  "findings": [
    {
      "title": "Finding title",
      "severity": "critical",
      "category": "broken_link",
      "description": "What is wrong and why it matters.",
      "evidence": [
        {
          "type": "wiki",
          "path": "<wiki-prefix>/topic/article.md",
          "link": "[[topic/article|Title]]",
          "note": "Evidence note."
        }
      ],
      "recommendation": "Concrete fix."
    }
  ],
  "coverage_gaps": [
    {
      "topic": "topic-slug",
      "description": "What is missing.",
      "suggested_action": "What to add or review."
    }
  ],
  "output": {
    "should_save": true,
    "filename_slug": "wiki-audit"
  },
  "review_notes": []
}
```

Allowed `severity`: `critical`, `warning`, `info`.
Allowed `category`: `broken_link`, `missing_reference`, `coverage_gap`, `quality`, `other`.
Audit is read-only by default.

### analyze: ticker -> report

**Intent**: produce a value + growth analysis for one ticker.

**Use**: `python3 scripts/analyze.py <ticker>`.

**Output**: `newswiki/outputs/<ticker>_analysis.md`.

Apply the investment lens: margin, FCF, leverage, PEG, moats, and risks.
