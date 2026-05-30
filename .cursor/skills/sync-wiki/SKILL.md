---
name: sync-wiki
description: Sync markdown from a configurable source directory into a structured wiki directory. Use when processing business/raw or another source directory into business/wiki, updating wiki indexes, archiving processed files, or running scripts/sync_wiki.py.
---

# Sync Wiki

## Purpose

Use this skill to sync raw source markdown into a structured wiki.

The model supplies judgment:
- topic mapping
- source-grounded distillation
- useful `[[wiki links]]`
- `[AI Synthesis]` labeling for inference

The harness supplies deterministic execution:
- source scanning
- JSON validation
- markdown rendering
- index updates
- archive status
- cache/idempotency

## Default Paths

For `dev.money`, the default layout is:

- Source: `business/raw`
- Wiki: `business/wiki`
- Archive: `<source>/archive`

Other layouts are valid. Treat `SOURCE`, `WIKI`, and `ARCHIVE` as execution parameters.

## Workflow

1. Read `GEMINI.md`, especially `Compile (raw -> wiki)`.
2. Run a dry sync first:

```bash
make sync-dry-run
```

3. Sync the default directories:

```bash
make sync
```

4. Sync custom directories:

```bash
make sync SOURCE=research/raw WIKI=research/wiki
```

5. Sync one file:

```bash
make sync-file FILE=2026-05-30-example.md
```

6. Verify after changes:

```bash
make test
```

## Direct Script Usage

Use the Makefile by default. If direct script usage is needed:

```bash
python3 scripts/sync_wiki.py \
  --source business/raw \
  --wiki business/wiki \
  --archive business/raw/archive
```

Dry run:

```bash
python3 scripts/sync_wiki.py \
  --source business/raw \
  --wiki business/wiki \
  --dry-run
```

## Rules

- Do not manually duplicate harness behavior in chat.
- Do not invent article facts.
- Preserve source language.
- Keep investment interpretation separate from source facts.
- Any unstated inference must start with `[AI Synthesis]`.
- Prefer existing topic folders before proposing a new one.
- Treat source, wiki, and archive paths as configurable execution inputs.
