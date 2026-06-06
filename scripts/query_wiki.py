"""Deterministic wiki query harness for dev.money."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from llm_provider import LLMProvider, LLMRequest, build_provider, proposal_from_provider


ROOT = Path(__file__).resolve().parent.parent
GEMINI_CONF = ROOT / "GEMINI.md"
DEFAULT_WIKI = "newswiki/wiki"
DEFAULT_OUTPUTS = "newswiki/outputs"
DEFAULT_SOURCE = "newswiki/raw"

AI_SYNTHESIS_PREFIX = "[AI Synthesis]"
CITATION_TYPES = {"wiki", "raw", "external"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _resolve_path(base: Path, value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def configure_paths(
    *,
    root: Path | None = None,
    wiki: Path | str | None = None,
    outputs: Path | str | None = None,
    source: Path | str | None = None,
) -> None:
    """Configure wiki, outputs, and source directories for the query harness."""

    global ROOT, WIKI_DIR, OUTPUTS_DIR, SOURCE_DIR, ROOT_INDEX
    global WIKI_PREFIX, SOURCE_PREFIX, OUTPUTS_PREFIX

    if root is not None:
        ROOT = root.resolve()

    if wiki is not None:
        WIKI_DIR = _resolve_path(ROOT, wiki)
    if outputs is not None:
        OUTPUTS_DIR = _resolve_path(ROOT, outputs)
    if source is not None:
        SOURCE_DIR = _resolve_path(ROOT, source)

    ROOT_INDEX = WIKI_DIR / "INDEX.md"
    WIKI_PREFIX = str(WIKI_DIR.relative_to(ROOT)).replace("\\", "/")
    SOURCE_PREFIX = str(SOURCE_DIR.relative_to(ROOT)).replace("\\", "/")
    OUTPUTS_PREFIX = str(OUTPUTS_DIR.relative_to(ROOT)).replace("\\", "/")


WIKI_DIR = ROOT / DEFAULT_WIKI
OUTPUTS_DIR = ROOT / DEFAULT_OUTPUTS
SOURCE_DIR = ROOT / DEFAULT_SOURCE
ROOT_INDEX = WIKI_DIR / "INDEX.md"
WIKI_PREFIX = DEFAULT_WIKI
SOURCE_PREFIX = DEFAULT_SOURCE
OUTPUTS_PREFIX = DEFAULT_OUTPUTS


@dataclass
class QueryResult:
    question: str
    output_path: str | None = None
    dry_run: bool = False
    saved: bool = False
    review_notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_wiki_context() -> str:
    """Load root and topic indexes as compact LLM context."""

    parts: list[str] = []
    if ROOT_INDEX.exists():
        parts.append(f"### Root INDEX ({WIKI_PREFIX}/INDEX.md)\n{ROOT_INDEX.read_text(encoding='utf-8').strip()}")

    for topic_dir in sorted(WIKI_DIR.iterdir()):
        if not topic_dir.is_dir():
            continue
        index_path = topic_dir / "_index.md"
        if not index_path.exists():
            continue
        rel = f"{WIKI_PREFIX}/{topic_dir.name}/_index.md"
        parts.append(f"### Topic Index ({rel})\n{index_path.read_text(encoding='utf-8').strip()}")

    return "\n\n".join(parts) if parts else "(no wiki indexes found)"


def build_query_prompt(question: str) -> LLMRequest:
    system = GEMINI_CONF.read_text(encoding="utf-8")
    prompt = f"""Answer this investment wiki question following the Query contract in GEMINI.md.

Question: {question}

Configured paths:
- Wiki prefix: {WIKI_PREFIX}/
- Source prefix: {SOURCE_PREFIX}/ (including {SOURCE_PREFIX}/archive/ for archived raw files)
- Outputs prefix: {OUTPUTS_PREFIX}/

Wiki index context:
{build_wiki_context()}

Return strict JSON only. Do not wrap the answer in markdown fences.
"""
    return LLMRequest(system=system, prompt=prompt)


def _require_mapping(response: dict[str, Any], key: str) -> dict[str, Any]:
    value = response.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Query field '{key}' must be an object.")
    return value


def _validate_synthesis_labels(items: list[str], label: str) -> None:
    for item in items:
        text = item.strip()
        if not text:
            raise ValueError(f"{label} contains an empty bullet.")
        if "AI Synthesis" in text and not text.startswith(AI_SYNTHESIS_PREFIX):
            raise ValueError(f"{label} inference must start with '{AI_SYNTHESIS_PREFIX}'.")


def _validate_citation(citation: dict[str, Any], index: int) -> None:
    ctype = citation.get("type")
    if ctype not in CITATION_TYPES:
        raise ValueError(f"citations[{index}] type must be one of {sorted(CITATION_TYPES)}.")

    note = str(citation.get("note", "")).strip()
    if not note:
        raise ValueError(f"citations[{index}].note is required.")

    if ctype == "external":
        url = str(citation.get("url", "")).strip()
        if not url.startswith("http"):
            raise ValueError(f"citations[{index}].url must be an http(s) URL.")
        return

    path = str(citation.get("path", "")).strip()
    link = str(citation.get("link", "")).strip()
    if not path:
        raise ValueError(f"citations[{index}].path is required for {ctype} citations.")
    if not link.startswith("[[") or "]]" not in link:
        raise ValueError(f"citations[{index}].link must be a clickable [[wiki link]].")

    if ctype == "wiki" and not path.startswith(f"{WIKI_PREFIX}/"):
        raise ValueError(f"citations[{index}].path must live under {WIKI_PREFIX}/.")
    if ctype == "raw" and not path.startswith(f"{SOURCE_PREFIX}/"):
        raise ValueError(f"citations[{index}].path must live under {SOURCE_PREFIX}/.")


def validate_query_response(response: dict[str, Any], question: str) -> None:
    if str(response.get("question", "")).strip() != question.strip():
        raise ValueError("question field must match the input question.")

    answer = _require_mapping(response, "answer")
    summary = str(answer.get("summary", "")).strip()
    sections = answer.get("sections", [])
    if not summary and not sections:
        raise ValueError("answer must include summary or sections.")

    if summary and "AI Synthesis" in summary and not summary.startswith(AI_SYNTHESIS_PREFIX):
        raise ValueError(f"answer.summary inference must start with '{AI_SYNTHESIS_PREFIX}'.")

    if sections is not None:
        if not isinstance(sections, list):
            raise ValueError("answer.sections must be a list.")
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("Each answer section must be an object.")
            heading = str(section.get("heading", "")).strip()
            bullets = section.get("bullets", [])
            if not heading:
                raise ValueError("Each answer section must include a heading.")
            if not isinstance(bullets, list) or not bullets:
                raise ValueError("Each answer section must include non-empty bullets.")
            _validate_synthesis_labels([str(b) for b in bullets], f"section '{heading}'")

    citations = response.get("citations", [])
    if not isinstance(citations, list) or not citations:
        raise ValueError("citations must be a non-empty list.")
    for index, citation in enumerate(citations):
        if not isinstance(citation, dict):
            raise ValueError(f"citations[{index}] must be an object.")
        _validate_citation(citation, index)

    output = _require_mapping(response, "output")
    if not isinstance(output.get("should_save"), bool):
        raise ValueError("output.should_save must be a boolean.")
    slug = str(output.get("filename_slug", "")).strip()
    if output.get("should_save") and slug and not SLUG_RE.fullmatch(slug):
        raise ValueError(f"output.filename_slug is invalid: {slug}")

    review_notes = response.get("review_notes", [])
    if review_notes is not None and not isinstance(review_notes, list):
        raise ValueError("review_notes must be a list.")


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _sanitize_slug(question: str, slug: str) -> str:
    if slug and SLUG_RE.fullmatch(slug):
        return slug
    safe = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    safe = re.sub(r"-+", "-", safe)
    return safe[:60] or "query"


def render_query_markdown(response: dict[str, Any]) -> str:
    answer = _require_mapping(response, "answer")
    question = str(response.get("question", "")).strip()
    today = date.today().isoformat()

    parts = [
        "---",
        f"title: {_yaml_quote(question)}",
        f"created: {today}",
        f"question: {_yaml_quote(question)}",
        "tags: [query-wiki]",
        "---",
        "",
        f"# {question}",
        "",
    ]

    summary = str(answer.get("summary", "")).strip()
    if summary:
        parts.extend(["## Summary", "", summary, ""])

    for section in answer.get("sections", []) or []:
        heading = str(section["heading"]).strip()
        parts.append(f"## {heading}")
        for bullet in section.get("bullets", []):
            parts.append(f"- {str(bullet).strip()}")
        parts.append("")

    parts.append("## Citations")
    for citation in response.get("citations", []):
        ctype = citation.get("type")
        note = str(citation.get("note", "")).strip()
        if ctype == "external":
            url = str(citation.get("url", "")).strip()
            parts.append(f"- **external**: [{url}]({url}) — {note}")
        else:
            link = str(citation.get("link", "")).strip()
            path = str(citation.get("path", "")).strip()
            parts.append(f"- **{ctype}**: {link} (`{path}`) — {note}")

    review_notes = response.get("review_notes") or []
    if review_notes:
        parts.extend(["", "## Review Notes"])
        for note in review_notes:
            parts.append(f"- {str(note).strip()}")

    return "\n".join(parts).strip() + "\n"


def save_query_output(response: dict[str, Any], *, dry_run: bool = False) -> Path | None:
    output = _require_mapping(response, "output")
    if not output.get("should_save"):
        return None

    question = str(response.get("question", "")).strip()
    slug = _sanitize_slug(question, str(output.get("filename_slug", "")).strip())
    target = OUTPUTS_DIR / f"{slug}-{date.today().isoformat()}.md"

    if dry_run:
        return target

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(render_query_markdown(response), encoding="utf-8")
    return target


def run_query(
    question: str,
    provider: LLMProvider,
    *,
    dry_run: bool = False,
    response: dict[str, Any] | None = None,
) -> QueryResult:
    result = QueryResult(question=question, dry_run=dry_run)
    try:
        resolved = response or proposal_from_provider(provider, build_query_prompt(question))
        validate_query_response(resolved, question)
        result.review_notes = [str(n) for n in resolved.get("review_notes", []) or []]

        markdown = render_query_markdown(resolved)
        if not dry_run and resolved.get("output", {}).get("should_save"):
            saved_path = save_query_output(resolved, dry_run=False)
            if saved_path:
                result.saved = True
                result.output_path = str(saved_path.relative_to(ROOT))
        elif dry_run:
            planned = save_query_output(resolved, dry_run=True)
            if planned:
                result.output_path = str(planned.relative_to(ROOT))

        if not result.output_path and resolved.get("output", {}).get("should_save"):
            slug = _sanitize_slug(
                question,
                str(resolved.get("output", {}).get("filename_slug", "")).strip(),
            )
            result.output_path = f"{OUTPUTS_PREFIX}/{slug}-{date.today().isoformat()}.md"

        if dry_run and not result.errors:
            result.review_notes.append(f"Rendered {len(markdown)} bytes (dry run).")
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def _format_result(result: QueryResult) -> str:
    parts = [f"question={result.question!r}"]
    if result.output_path:
        parts.append(f"output={result.output_path}")
    if result.saved:
        parts.append("saved=yes")
    if result.dry_run:
        parts.append("dry_run=yes")
    if result.review_notes:
        parts.append("notes=" + "; ".join(result.review_notes))
    if result.errors:
        parts.append("errors=" + "; ".join(result.errors))
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the investment wiki with LLM synthesis.")
    parser.add_argument("--wiki", default=DEFAULT_WIKI, help="Wiki directory.")
    parser.add_argument("--outputs", default=DEFAULT_OUTPUTS, help="Directory for saved query outputs.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Raw source directory for evidence links.")
    parser.add_argument("--question", required=True, help="Question to answer from wiki evidence.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and render without saving output.")
    parser.add_argument("--provider", default="openai", choices=["openai", "fixture"], help="LLM provider backend.")
    args = parser.parse_args()

    configure_paths(wiki=args.wiki, outputs=args.outputs, source=args.source)

    if args.provider == "fixture":
        print("[query_wiki] fixture provider requires injecting responses in tests or API calls.")
        return 1

    provider = build_provider(args.provider)
    result = run_query(args.question, provider, dry_run=args.dry_run)
    print(f"[query_wiki] {_format_result(result)}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
