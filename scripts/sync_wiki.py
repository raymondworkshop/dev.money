"""Deterministic raw -> wiki sync harness for dev.money."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from llm_provider import LLMProvider, LLMRequest, build_provider, proposal_from_provider


ROOT = Path(__file__).resolve().parent.parent
GEMINI_CONF = ROOT / "GEMINI.md"
DEFAULT_SOURCE = "business/raw"
DEFAULT_WIKI = "business/wiki"


def _resolve_path(base: Path, value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def configure_paths(
    *,
    root: Path | None = None,
    source: Path | str | None = None,
    wiki: Path | str | None = None,
    archive: Path | str | None = None,
) -> None:
    """Configure source, wiki, and archive directories for the sync harness."""

    global ROOT, RAW_DIR, ARCHIVE_DIR, WIKI_DIR, CACHE_PATH, STATUS_PATH, ROOT_INDEX
    global SOURCE_PREFIX, WIKI_PREFIX

    if root is not None:
        ROOT = root.resolve()

    if source is not None:
        RAW_DIR = _resolve_path(ROOT, source)
    if wiki is not None:
        WIKI_DIR = _resolve_path(ROOT, wiki)
    if archive is not None:
        ARCHIVE_DIR = _resolve_path(ROOT, archive)
    elif source is not None:
        ARCHIVE_DIR = RAW_DIR / "archive"

    CACHE_PATH = ARCHIVE_DIR / ".sync_cache.json"
    STATUS_PATH = ARCHIVE_DIR / "STATUS.md"
    ROOT_INDEX = WIKI_DIR / "INDEX.md"
    SOURCE_PREFIX = str(RAW_DIR.relative_to(ROOT)).replace("\\", "/")
    WIKI_PREFIX = str(WIKI_DIR.relative_to(ROOT)).replace("\\", "/")


RAW_DIR = ROOT / DEFAULT_SOURCE
ARCHIVE_DIR = RAW_DIR / "archive"
WIKI_DIR = ROOT / DEFAULT_WIKI
CACHE_PATH = ARCHIVE_DIR / ".sync_cache.json"
STATUS_PATH = ARCHIVE_DIR / "STATUS.md"
ROOT_INDEX = WIKI_DIR / "INDEX.md"
SOURCE_PREFIX = DEFAULT_SOURCE
WIKI_PREFIX = DEFAULT_WIKI

ALLOWED_ACTIONS = {"create_article", "skip_duplicate", "needs_review"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
AI_SYNTHESIS_PREFIX = "[AI Synthesis]"


@dataclass
class CompileResult:
    source_file: str
    action: str
    article_path: str | None = None
    archived: bool = False
    dry_run: bool = False
    review_notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, str]) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scan_pending_files(*, include_cached: bool = False) -> list[Path]:
    """Return unarchived markdown files under the configured source directory."""

    cache = load_cache()
    pending: list[Path] = []
    for path in sorted(RAW_DIR.glob("*.md")):
        rel = path.name
        if include_cached or cache.get(rel) != _file_hash(path):
            pending.append(path)
    return pending


def parse_raw_front_matter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML-like front matter from raw markdown body."""

    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not match:
        return {}, content

    front_matter: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - "):
            authors = front_matter.get("author")
            if isinstance(authors, list):
                authors.append(line[4:].strip().strip('"'))
            else:
                front_matter["author"] = [line[4:].strip().strip('"')]
            continue
        key_match = re.match(r"^(\w+):\s*(.*)$", line)
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip().strip('"')
        if key == "author" and not value:
            front_matter[key] = []
        else:
            front_matter[key] = value

    body = content[match.end() :]
    return front_matter, body


def list_topic_context() -> str:
    """Build a compact index of existing wiki topics for LLM context."""

    lines: list[str] = []
    for topic_dir in sorted(WIKI_DIR.iterdir()):
        if not topic_dir.is_dir():
            continue
        index_path = topic_dir / "_index.md"
        if index_path.exists():
            first_line = index_path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            lines.append(f"- {topic_dir.name}: {first_line}")
    return "\n".join(lines)


def build_compile_prompt(raw_path: Path) -> LLMRequest:
    content = raw_path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(content)
    rel = f"{SOURCE_PREFIX}/{raw_path.name}"
    system = GEMINI_CONF.read_text(encoding="utf-8")
    prompt = f"""Compile this raw source into one JSON proposal following the contract in GEMINI.md.

Source file: {rel}
Existing topics:
{list_topic_context() or "- none"}

Raw front matter:
{json.dumps(front_matter, ensure_ascii=False, indent=2)}

Raw body:
---
{body.strip()}
---
"""
    return LLMRequest(system=system, prompt=prompt)


def _require_mapping(proposal: dict[str, Any], key: str) -> dict[str, Any]:
    value = proposal.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Proposal field '{key}' must be an object.")
    return value


def _validate_slug(slug: str, label: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"{label} slug is invalid: {slug}")


def _validate_synthesis_labels(items: list[str], label: str) -> None:
    for item in items:
        text = item.strip()
        if not text:
            raise ValueError(f"{label} contains an empty bullet.")
        if "AI Synthesis" in text and not text.startswith(AI_SYNTHESIS_PREFIX):
            raise ValueError(f"{label} inference must start with '{AI_SYNTHESIS_PREFIX}'.")


def validate_proposal(proposal: dict[str, Any], raw_path: Path) -> None:
    action = proposal.get("action")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")

    source_file = proposal.get("source_file")
    expected = f"{SOURCE_PREFIX}/{raw_path.name}"
    if source_file != expected:
        raise ValueError(f"source_file must be '{expected}', got '{source_file}'.")

    review_notes = proposal.get("review_notes", [])
    if review_notes is not None and not isinstance(review_notes, list):
        raise ValueError("review_notes must be a list.")

    if action != "create_article":
        return

    topic = _require_mapping(proposal, "topic")
    article = _require_mapping(proposal, "article")
    index_updates = _require_mapping(proposal, "index_updates")
    archive = _require_mapping(proposal, "archive")

    _validate_slug(str(topic.get("slug", "")), "topic")
    _validate_slug(str(article.get("slug", "")), "article")

    article_path = Path(str(article.get("path", "")))
    wiki_prefix = f"{WIKI_PREFIX}/"
    if not str(article_path).startswith(wiki_prefix):
        raise ValueError(f"article.path must live under {wiki_prefix}.")

    front_matter = article.get("front_matter")
    if not isinstance(front_matter, dict) or not front_matter.get("title"):
        raise ValueError("article.front_matter.title is required.")

    sections = article.get("sections", [])
    if not isinstance(sections, list) or not sections:
        raise ValueError("article.sections must be a non-empty list.")

    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Each section must be an object.")
        bullets = section.get("bullets", [])
        if not isinstance(bullets, list) or not bullets:
            raise ValueError("Each section must include non-empty bullets.")
        _validate_synthesis_labels([str(b) for b in bullets], "section bullet")

    key_takeaways = article.get("key_takeaways", [])
    if not isinstance(key_takeaways, list) or not key_takeaways:
        raise ValueError("article.key_takeaways must be a non-empty list.")
    _validate_synthesis_labels([str(k) for k in key_takeaways], "key takeaway")

    for key in ("topic_index_entry", "root_recent_entry"):
        if not str(index_updates.get(key, "")).strip():
            raise ValueError(f"index_updates.{key} is required.")

    if archive.get("should_archive") is not True:
        raise ValueError("archive.should_archive must be true for create_article.")
    if not str(archive.get("status_row", "")).strip():
        raise ValueError("archive.status_row is required.")


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_front_matter(front_matter: dict[str, Any]) -> str:
    lines = ["---"]
    for key in ("title", "source", "published", "created", "description"):
        if key in front_matter and front_matter[key]:
            lines.append(f"{key}: {_yaml_quote(str(front_matter[key]))}")

    authors = front_matter.get("author", [])
    if isinstance(authors, str):
        authors = [authors]
    if authors:
        lines.append("author:")
        for author in authors:
            author_text = str(author).strip()
            if not author_text.startswith('"'):
                author_text = _yaml_quote(author_text)
            lines.append(f"  - {author_text}")

    lines.append("---")
    return "\n".join(lines)


def render_article_markdown(proposal: dict[str, Any]) -> str:
    article = _require_mapping(proposal, "article")
    front_matter = article["front_matter"]
    title = str(article.get("title") or front_matter.get("title", "")).strip()
    parts = [_format_front_matter(front_matter), "", f"# {title}", ""]

    for section in article["sections"]:
        heading = str(section["heading"]).strip()
        parts.append(f"## {heading}")
        for bullet in section["bullets"]:
            parts.append(f"- {str(bullet).strip()}")
        parts.append("")

    parts.append("## Key Takeaways")
    for takeaway in article["key_takeaways"]:
        parts.append(f"- {str(takeaway).strip()}")
    parts.append("")

    footer = article.get("topic_footer", {})
    topic_link = str(footer.get("topic_link", "")).strip()
    tags = footer.get("tags", [])
    tag_line = " ".join(str(tag).strip() for tag in tags if str(tag).strip())
    parts.extend(["---", f"**Topic**: {topic_link}  ", f"**Tags**: {tag_line}"])
    return "\n".join(parts).strip() + "\n"


def _append_unique_line(path: Path, section_heading: str, line: str) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    normalized = line.strip()
    if normalized in content:
        return

    marker = f"## {section_heading}"
    if marker in content:
        before, after = content.split(marker, 1)
        updated = before.rstrip() + f"\n\n{marker}\n{normalized}\n" + after.lstrip("\n")
    else:
        updated = content.rstrip() + f"\n\n{marker}\n{normalized}\n"
    path.write_text(updated, encoding="utf-8")


def _prepend_recent_article(entry: str) -> None:
    content = ROOT_INDEX.read_text(encoding="utf-8")
    normalized = entry.strip()
    if normalized in content:
        return

    marker = "## Recent Articles"
    if marker not in content:
        raise ValueError("Root INDEX.md is missing '## Recent Articles'.")
    before, after = content.split(marker, 1)
    lines = after.splitlines()
    insert_at = 1 if lines and not lines[0].strip() else 0
    lines.insert(insert_at, normalized)
    updated = before.rstrip() + f"\n\n{marker}\n" + "\n".join(lines)
    if not updated.endswith("\n"):
        updated += "\n"
    ROOT_INDEX.write_text(updated, encoding="utf-8")


def ensure_topic_index(proposal: dict[str, Any]) -> Path:
    topic = _require_mapping(proposal, "topic")
    topic_dir = WIKI_DIR / str(topic["slug"])
    topic_dir.mkdir(parents=True, exist_ok=True)
    index_path = topic_dir / "_index.md"
    if index_path.exists():
        return index_path

    title = str(topic.get("title", topic["slug"]))
    rationale = str(topic.get("rationale", "")).strip()
    overview = rationale or f"{title} related articles and investment notes."
    stub = f"""# {title}

## 概述
{overview}

## 核心指标
- **关键公司**:
- **关键技术/变量**:
- **投资视角**:

## 相关文章

## 相关主题
"""
    index_path.write_text(stub.strip() + "\n", encoding="utf-8")
    return index_path


def update_indexes(proposal: dict[str, Any]) -> None:
    index_updates = _require_mapping(proposal, "index_updates")
    topic_index = ensure_topic_index(proposal)
    _append_unique_line(topic_index, "相关文章", str(index_updates["topic_index_entry"]).strip())
    _prepend_recent_article(str(index_updates["root_recent_entry"]).strip())


def append_status_row(status_row: str) -> None:
    row = status_row.strip()
    if STATUS_PATH.exists() and row in STATUS_PATH.read_text(encoding="utf-8"):
        return

    if STATUS_PATH.exists():
        content = STATUS_PATH.read_text(encoding="utf-8")
        updated = content.replace(
            "**Last Updated:**",
            f"**Last Updated:** {date.today().isoformat()}",
            1,
        )
        if updated == content:
            updated = f"**Last Updated:** {date.today().isoformat()}\n\n" + content
    else:
        updated = f"# Archive Status\n\n**Last Updated:** {date.today().isoformat()}\n\n"

    if "| File | Topic | Wiki Location | Status |" in updated:
        updated = updated.replace(
            "| File | Topic | Wiki Location | Status |\n|------|-------|---------------|--------|",
            "| File | Topic | Wiki Location | Status |\n|------|-------|---------------|--------|\n" + row,
            1,
        )
    else:
        updated += f"\n| File | Topic | Wiki Location | Status |\n|------|-------|---------------|--------|\n{row}\n"

    STATUS_PATH.write_text(updated, encoding="utf-8")


def archive_source(raw_path: Path) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / raw_path.name
    if target.exists():
        return
    shutil.move(str(raw_path), str(target))


def apply_proposal(
    proposal: dict[str, Any],
    raw_path: Path,
    *,
    dry_run: bool = False,
    no_archive: bool = False,
) -> CompileResult:
    validate_proposal(proposal, raw_path)
    action = str(proposal["action"])
    result = CompileResult(
        source_file=raw_path.name,
        action=action,
        dry_run=dry_run,
        review_notes=[str(n) for n in proposal.get("review_notes", []) or []],
    )

    if action in {"skip_duplicate", "needs_review"}:
        return result

    article = _require_mapping(proposal, "article")
    article_path = ROOT / str(article["path"])
    result.article_path = str(article_path.relative_to(ROOT))

    if dry_run:
        return result

    article_path.parent.mkdir(parents=True, exist_ok=True)
    article_path.write_text(render_article_markdown(proposal), encoding="utf-8")
    update_indexes(proposal)

    archive = _require_mapping(proposal, "archive")
    if archive.get("should_archive") and not no_archive:
        append_status_row(str(archive["status_row"]))
        archive_source(raw_path)
        result.archived = True

    cache = load_cache()
    cache[raw_path.name] = _file_hash(ARCHIVE_DIR / raw_path.name) if result.archived else _file_hash(raw_path)
    save_cache(cache)
    return result


def sync_file(
    raw_path: Path,
    provider: LLMProvider,
    *,
    dry_run: bool = False,
    no_archive: bool = False,
    proposal: dict[str, Any] | None = None,
) -> CompileResult:
    try:
        resolved = proposal or proposal_from_provider(provider, build_compile_prompt(raw_path))
        return apply_proposal(resolved, raw_path, dry_run=dry_run, no_archive=no_archive)
    except Exception as exc:
        return CompileResult(
            source_file=raw_path.name,
            action="error",
            dry_run=dry_run,
            errors=[str(exc)],
        )


def run_sync(
    *,
    files: list[Path] | None = None,
    provider: LLMProvider | None = None,
    dry_run: bool = False,
    no_archive: bool = False,
    include_cached: bool = False,
) -> list[CompileResult]:
    targets = files or scan_pending_files(include_cached=include_cached)
    if not targets:
        return []

    llm = provider or build_provider("openai")
    results: list[CompileResult] = []
    for raw_path in targets:
        results.append(
            sync_file(raw_path, llm, dry_run=dry_run, no_archive=no_archive)
        )
    return results


compile_file = sync_file
run_compile = run_sync


def _format_result(result: CompileResult) -> str:
    parts = [f"{result.source_file}: action={result.action}"]
    if result.article_path:
        parts.append(f"article={result.article_path}")
    if result.archived:
        parts.append("archived=yes")
    if result.dry_run:
        parts.append("dry_run=yes")
    if result.review_notes:
        parts.append("notes=" + "; ".join(result.review_notes))
    if result.errors:
        parts.append("errors=" + "; ".join(result.errors))
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync source markdown into structured wiki articles.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source directory for raw markdown.")
    parser.add_argument("--wiki", default=DEFAULT_WIKI, help="Destination wiki directory.")
    parser.add_argument("--archive", default=None, help="Archive directory (defaults to <source>/archive).")
    parser.add_argument("--file", action="append", dest="files", help="Sync one raw filename or path.")
    parser.add_argument("--all", action="store_true", help="Include files already present in sync cache.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and render plan without writing files.")
    parser.add_argument("--no-archive", action="store_true", help="Write wiki output but keep raw files in place.")
    parser.add_argument("--provider", default="openai", choices=["openai", "fixture"], help="LLM provider backend.")
    args = parser.parse_args()

    configure_paths(
        source=args.source,
        wiki=args.wiki,
        archive=args.archive or str(Path(args.source) / "archive"),
    )

    selected: list[Path] | None = None
    if args.files:
        selected = []
        for item in args.files:
            path = Path(item)
            if not path.is_absolute():
                path = RAW_DIR / path.name if path.parent == Path(".") else ROOT / path
            selected.append(path)

    provider = build_provider(args.provider) if args.provider != "fixture" else None
    if args.provider == "fixture":
        print("[sync_wiki] fixture provider requires injecting proposals in tests or API calls.")
        return 1

    results = run_sync(
        files=selected,
        provider=provider,
        dry_run=args.dry_run,
        no_archive=args.no_archive,
        include_cached=args.all,
    )
    if not results:
        print("[sync_wiki] nothing to sync.")
        return 0

    exit_code = 0
    for result in results:
        print(f"[sync_wiki] {_format_result(result)}")
        if result.errors:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
