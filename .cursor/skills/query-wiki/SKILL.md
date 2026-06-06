---
name: query-wiki
description: Answer investment questions from the structured wiki with cited evidence. Use when querying newswiki/wiki, searching knowledge base topics, synthesizing wiki articles, running scripts/query_wiki.py, or make query.
---

# Query Wiki

## Purpose

Use this skill to answer questions from the investment wiki with provenance.

The model supplies judgment:
- interpret the question and choose relevant evidence
- synthesize wiki articles into a coherent answer
- cite wiki pages, raw sources, and external URLs
- label inference with `[AI Synthesis]`

The harness supplies deterministic execution:
- load wiki indexes
- build the LLM prompt from `GEMINI.md`
- validate JSON responses
- render markdown output
- save results to the outputs directory

## Default Paths

For `dev.money`, the default layout is:

- Wiki: `newswiki/wiki`
- Outputs: `newswiki/outputs`
- Source: `newswiki/raw` (including `newswiki/raw/archive` for provenance links)

Other layouts are valid. Treat `WIKI`, `OUTPUTS`, and `SOURCE` as execution parameters.

## Workflow

1. Read `GEMINI.md`, especially `Query (wiki -> answer)`.
2. Run a dry query first:

```bash
make query-dry-run QUESTION="How does Nebius compare to CoreWeave?"
```

3. Run a live query:

```bash
make query QUESTION="What are the stablecoin risks covered in the wiki?"
```

4. Query custom directories:

```bash
make query WIKI=research/wiki OUTPUTS=research/outputs SOURCE=research/raw QUESTION="..."
```

5. Verify after changes:

```bash
make test
```

## Direct Script Usage

Use the Makefile by default. If direct script usage is needed:

```bash
python3 scripts/query_wiki.py \
  --wiki newswiki/wiki \
  --outputs newswiki/outputs \
  --source newswiki/raw \
  --question "How does Nebius compare to CoreWeave?"
```

Dry run:

```bash
python3 scripts/query_wiki.py \
  --wiki newswiki/wiki \
  --outputs newswiki/outputs \
  --source newswiki/raw \
  --question "What stablecoin risks are documented?" \
  --dry-run
```

## Answer Rules

- Ground answers in wiki evidence first; use raw files for provenance and verification.
- Include external URLs from article front matter when they strengthen citations.
- Do not invent facts, figures, dates, companies, or quotes.
- Any unstated inference must start with `[AI Synthesis]`.
- Return strict JSON only. Do not wrap the answer in markdown.

## Evidence Rules

- **Wiki** is the primary evidence layer. Cite with clickable `[[topic/article-slug|Title]]` links.
- **Raw** files support verification. Prefer archive paths such as `[[../raw/archive/file.md|original]]` relative to wiki pages, or repo-root paths in `citations[].path`.
- **External** URLs come from front matter `source` fields when needed.

## Output Shape

Saved markdown includes:
- question title and summary
- answer sections with bullets
- a citations section listing wiki, raw, and external evidence

The harness saves to `<outputs>/<filename_slug>-YYYY-MM-DD.md` when `output.should_save` is true.

## Rules

- Do not manually duplicate harness behavior in chat.
- Do not answer from memory when the wiki should be queried.
- Keep investment interpretation separate from source facts.
- Treat wiki, outputs, and source paths as configurable execution inputs.
