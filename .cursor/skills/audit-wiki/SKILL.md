---
name: audit-wiki
description: Audit the investment wiki for broken links, missing references, and coverage gaps. Use when reviewing newswiki/wiki quality, running scripts/audit_wiki.py, or make audit.
---

# Audit Wiki

## Purpose

Use this skill to produce a read-only quality report for the investment wiki.

The model supplies judgment:
- interpret deterministic harness findings
- identify coverage gaps and quality issues
- cite wiki pages, raw sources, and external URLs
- recommend fixes without modifying files

The harness supplies deterministic execution:
- scan wiki markdown for `[[links]]`
- resolve link targets within the wiki and raw archive
- detect index reference gaps
- build file inventory for prompt context
- validate JSON responses
- render markdown audit reports
- save results to the outputs directory

## Default Paths

For `dev.money`, the default layout is:

- Wiki: `newswiki/wiki`
- Source: `newswiki/raw` (including `newswiki/raw/archive` for provenance links)
- Outputs: `newswiki/outputs`

Other layouts are valid. Treat `WIKI`, `SOURCE`, and `OUTPUTS` as execution parameters.

## Workflow

1. Read `AGENTS.md`, especially `audit-wiki: wiki -> quality report`.
2. Run a dry audit first:

```bash
make audit-dry-run
```

3. Run a live audit:

```bash
make audit
```

4. Audit custom directories:

```bash
make audit WIKI=research/wiki SOURCE=research/raw OUTPUTS=research/outputs
```

5. Verify after changes:

```bash
make test
```

## Direct Script Usage

Use the Makefile by default. If direct script usage is needed:

```bash
python3 scripts/audit_wiki.py \
  --wiki newswiki/wiki \
  --source newswiki/raw \
  --outputs newswiki/outputs
```

Dry run:

```bash
python3 scripts/audit_wiki.py \
  --wiki newswiki/wiki \
  --source newswiki/raw \
  --outputs newswiki/outputs \
  --dry-run
```

## Audit Rules

- Read-only by default. Do not modify wiki or raw files unless explicitly directed.
- Ground findings in wiki evidence first; use raw files for provenance and verification.
- Include external URLs from article front matter when they strengthen citations.
- Do not invent facts, figures, dates, companies, or quotes.
- Return strict JSON only. Do not wrap the answer in markdown.

## Evidence Rules

- **Wiki** is the primary evidence layer. Cite with clickable `[[topic/article-slug|Title]]` links.
- **Raw** files support verification. Prefer archive paths such as `[[../raw/archive/file.md|original]]` relative to wiki pages, or repo-root paths in `findings[].evidence[].path`.
- **External** URLs come from front matter `source` fields when needed.

## Output Shape

Saved markdown includes:
- audit summary
- findings grouped by severity and category
- coverage gaps
- harness deterministic check summary

The harness saves to `<outputs>/<filename_slug>-YYYY-MM-DD.md` when `output.should_save` is true.

## Rules

- Do not manually duplicate harness behavior in chat.
- Do not edit wiki files while auditing unless the user explicitly requests fixes.
- Treat wiki, source, and outputs paths as configurable execution inputs.
