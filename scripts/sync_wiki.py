"""Deterministic raw -> wiki sync harness for dev.news-wiki."""

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

from llm_provider import LLMProvider, LLMRequest, build_provider, default_provider, proposal_from_provider


ROOT = Path(__file__).resolve().parent.parent
AGENTS_CONF = ROOT / "AGENTS.md"
DEFAULT_SOURCE = "newswiki/raw"
DEFAULT_WIKI = "newswiki/wiki"


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
    resources: Path | str | None = None,
) -> None:
    """Configure source, wiki, archive, and resources directories for the sync harness."""

    global ROOT, RAW_DIR, ARCHIVE_DIR, WIKI_DIR, RESOURCES_DIR, CACHE_PATH, STATUS_PATH, ROOT_INDEX
    global SOURCE_PREFIX, WIKI_PREFIX, SYNC_LOG_PATH

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

    if resources is not None:
        RESOURCES_DIR = _resolve_path(ROOT, resources)
    elif source is not None:
        RESOURCES_DIR = RAW_DIR.parent / "_resources"

    CACHE_PATH = ARCHIVE_DIR / ".sync_cache.json"
    STATUS_PATH = ARCHIVE_DIR / "STATUS.md"
    ROOT_INDEX = WIKI_DIR / "INDEX.md"
    SOURCE_PREFIX = str(RAW_DIR.relative_to(ROOT)).replace("\\", "/")
    WIKI_PREFIX = str(WIKI_DIR.relative_to(ROOT)).replace("\\", "/")
    SYNC_LOG_PATH = ROOT / "logs" / "sync.log"


RAW_DIR = ROOT / DEFAULT_SOURCE
ARCHIVE_DIR = RAW_DIR / "archive"
WIKI_DIR = ROOT / DEFAULT_WIKI
RESOURCES_DIR = RAW_DIR.parent / "_resources"
CACHE_PATH = ARCHIVE_DIR / ".sync_cache.json"
STATUS_PATH = ARCHIVE_DIR / "STATUS.md"
ROOT_INDEX = WIKI_DIR / "INDEX.md"
SOURCE_PREFIX = DEFAULT_SOURCE
WIKI_PREFIX = DEFAULT_WIKI
SYNC_LOG_PATH = ROOT / "logs" / "sync.log"

ALLOWED_ACTIONS = {"create_article", "skip_duplicate", "needs_review"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
AI_SYNTHESIS_PREFIX = "[AI Synthesis]"
RESOURCE_DIR_RE = re.compile(r"_resources/([^/\]\s]+)")
TRUNCATED_URL_RE = re.compile(r"\.\.\.")
WIKI_PATH_RE = re.compile(r"`([^`]+\.md)`")


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
    system = AGENTS_CONF.read_text(encoding="utf-8")
    prompt = f"""Compile this raw source into one JSON proposal following the contract in AGENTS.md.

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
    if not str(front_matter.get("source", "")).strip():
        raise ValueError("article.front_matter.source is required for create_article.")


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _markdown_external_link(label: str, url: str) -> str:
    """Render an external citation as a markdown link."""

    safe_label = label.replace("[", "\\[").replace("]", "\\]")
    return f"[{safe_label}]({url})"


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
    source = str(front_matter.get("source", "")).strip()
    heading = f"# {_markdown_external_link(title, source)}" if source else f"# {title}"
    parts = [_format_front_matter(front_matter), "", heading, ""]

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


def is_truncated_url(url: str) -> bool:
    """Return True when a URL was shortened with ellipsis."""

    return bool(TRUNCATED_URL_RE.search(url.strip()))


def raw_source_url(raw_path: Path) -> str:
    """Read the provenance source URL from a raw markdown file."""

    if not raw_path.exists():
        return ""
    raw_front, _ = parse_raw_front_matter(raw_path.read_text(encoding="utf-8"))
    return str(raw_front.get("source", "")).strip()


def article_source_url(proposal: dict[str, Any], raw_path: Path | None = None) -> str:
    """Return the external source URL, preferring raw provenance over LLM output."""

    article = _require_mapping(proposal, "article")
    front_matter = article.get("front_matter", {})
    proposal_source = str(front_matter.get("source", "")).strip()

    if raw_path is not None:
        raw_source = raw_source_url(raw_path)
        if raw_source:
            return raw_source

    return proposal_source


def normalize_wiki_path(path: str, *, topic_slug: str = "") -> str:
    """Ensure a wiki path includes the configured wiki prefix."""

    normalized = path.strip().replace("\\", "/").lstrip("/")
    wiki_prefix = WIKI_PREFIX.replace("\\", "/")
    full_prefix = f"{wiki_prefix}/"
    if normalized.startswith(full_prefix):
        return normalized
    if normalized.startswith("wiki/"):
        normalized = normalized[len("wiki/") :]
        if normalized.startswith(full_prefix):
            return normalized
    if "/" not in normalized and topic_slug:
        return f"{full_prefix}{topic_slug}/{normalized}"
    return f"{full_prefix}{normalized}"


def normalize_proposal_paths(proposal: dict[str, Any]) -> None:
    """Repair topic/article paths when the LLM omits the wiki directory prefix."""

    if proposal.get("action") != "create_article":
        return

    topic = _require_mapping(proposal, "topic")
    article = _require_mapping(proposal, "article")
    topic_slug = str(topic.get("slug", "")).strip()
    article_slug = str(article.get("slug", "")).strip()

    topic_path = str(topic.get("path", "")).strip()
    if topic_path:
        topic["path"] = normalize_wiki_path(topic_path, topic_slug=topic_slug)
    elif topic_slug:
        topic["path"] = normalize_wiki_path(topic_slug, topic_slug=topic_slug)

    article_path = str(article.get("path", "")).strip()
    if article_path:
        article["path"] = normalize_wiki_path(article_path, topic_slug=topic_slug)
    elif topic_slug and article_slug:
        article["path"] = normalize_wiki_path(
            f"{topic_slug}/{article_slug}.md",
            topic_slug=topic_slug,
        )


def normalize_proposal_source(proposal: dict[str, Any], raw_path: Path) -> None:
    """Overwrite proposal source with raw provenance before rendering."""

    source = article_source_url(proposal, raw_path)
    if not source:
        return
    article = _require_mapping(proposal, "article")
    front_matter = article.setdefault("front_matter", {})
    front_matter["source"] = source


def build_status_row(proposal: dict[str, Any], raw_path: Path) -> str:
    """Build a STATUS.md row using the wiki article path as Wiki Location."""

    topic = _require_mapping(proposal, "topic")
    article = _require_mapping(proposal, "article")
    topic_title = str(topic.get("title", topic["slug"])).strip()
    article_path = str(article.get("path", "")).strip()
    if not article_path:
        raise ValueError("article.path is required for archive status.")
    return f"| {raw_path.name} | {topic_title} | `{article_path}` | Archived |"


def render_archive_stub(proposal: dict[str, Any], raw_path: Path) -> str:
    """Write a provenance stub with source link instead of full raw text."""

    article = _require_mapping(proposal, "article")
    front_matter = article.get("front_matter", {})
    source = article_source_url(proposal, raw_path)
    if not source:
        raise ValueError("article.front_matter.source is required for archive stub.")

    title = str(article.get("title") or front_matter.get("title", raw_path.stem)).strip()
    lines = [
        "---",
        f"title: {_yaml_quote(title)}",
        f"source: {_yaml_quote(source)}",
    ]
    for key in ("published", "created"):
        if front_matter.get(key):
            lines.append(f"{key}: {_yaml_quote(str(front_matter[key]))}")
    lines.extend(
        [
            "---",
            "",
            "Provenance stub. Synced to wiki; full article at `source` above.",
            "",
        ]
    )
    return "\n".join(lines)


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


def resource_dirs_for_raw(raw_path: Path) -> list[Path]:
    """Return `_resources/<folder>` directories referenced by a raw source file."""

    dirs: set[Path] = set()
    if raw_path.exists():
        for match in RESOURCE_DIR_RE.finditer(raw_path.read_text(encoding="utf-8")):
            dirs.add(RESOURCES_DIR / match.group(1))

    default_dir = RESOURCES_DIR / raw_path.stem
    if default_dir.exists():
        dirs.add(default_dir)

    return sorted(dirs)


def remove_raw_resources(raw_path: Path) -> list[Path]:
    """Delete `_resources` folders tied to a processed raw source file."""

    removed: list[Path] = []
    for resource_dir in resource_dirs_for_raw(raw_path):
        if resource_dir.is_dir():
            shutil.rmtree(resource_dir)
            removed.append(resource_dir)
    return removed


def remove_raw_source(raw_path: Path) -> None:
    """Delete a processed raw inbox file and its related `_resources` folders."""

    remove_raw_resources(raw_path)
    if raw_path.exists():
        raw_path.unlink()


def archive_source(raw_path: Path, proposal: dict[str, Any]) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / raw_path.name
    if target.exists():
        return
    target.write_text(render_archive_stub(proposal, raw_path), encoding="utf-8")


def apply_proposal(
    proposal: dict[str, Any],
    raw_path: Path,
    *,
    dry_run: bool = False,
    no_archive: bool = False,
) -> CompileResult:
    normalize_proposal_paths(proposal)
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

    normalize_proposal_source(proposal, raw_path)

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
        append_status_row(build_status_row(proposal, raw_path))
        archive_source(raw_path, proposal)
        result.archived = True

    remove_raw_source(raw_path)

    cache = load_cache()
    if result.archived:
        cache[raw_path.name] = _file_hash(ARCHIVE_DIR / raw_path.name)
    else:
        cache[raw_path.name] = _file_hash(article_path)
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

    llm = provider or build_provider(default_provider())
    results: list[CompileResult] = []
    for raw_path in targets:
        log_sync_event("START", raw_path.name)
        result = sync_file(raw_path, llm, dry_run=dry_run, no_archive=no_archive)
        results.append(result)
        if result.errors:
            log_sync_event(
                "ERROR",
                f"{raw_path.name}: {'; '.join(result.errors)} (continuing)",
            )
        else:
            print(f"[sync_wiki] {_format_result(result)}", flush=True)
            append_sync_log(f"[sync_wiki] {_format_result(result)}")
    return results


compile_file = sync_file
run_compile = run_sync


def _normalize_archive_filename(name: str) -> str:
    """Normalize quote variants so STATUS rows match archive filenames."""

    return (
        name.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def resolve_archive_path(archive_name: str) -> Path | None:
    """Resolve an archive markdown path, tolerating quote mismatches in STATUS.md."""

    direct = ARCHIVE_DIR / archive_name
    if direct.exists():
        return direct

    normalized = _normalize_archive_filename(archive_name)
    for candidate in ARCHIVE_DIR.glob("*.md"):
        if candidate.name == normalized or _normalize_archive_filename(candidate.name) == normalized:
            return candidate
    return None


def parse_status_wiki_archive_map() -> dict[Path, Path]:
    """Map wiki article paths to archive files using STATUS.md rows."""

    if not STATUS_PATH.exists():
        return {}

    mapping: dict[Path, Path] = {}
    for line in STATUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "Wiki Location" in line or line.startswith("|------"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 3:
            continue

        archive_name = parts[0]
        wiki_match = WIKI_PATH_RE.search(parts[2])
        if not wiki_match:
            continue

        wiki_path = ROOT / wiki_match.group(1)
        archive_path = resolve_archive_path(archive_name)
        if wiki_path.exists() and archive_path is not None:
            mapping[wiki_path] = archive_path
    return mapping


def update_wiki_source(path: Path, source: str) -> bool:
    """Replace front matter and H1 source links in one wiki article."""

    content = path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(content)
    title = str(front_matter.get("title", "")).strip()
    old_source = str(front_matter.get("source", "")).strip()
    if not title or old_source == source:
        return False

    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if not match:
        return False

    front_block = match.group(0)
    new_front_block = re.sub(
        r'^source:\s*".*"$',
        f"source: {_yaml_quote(source)}",
        front_block,
        count=1,
        flags=re.MULTILINE,
    )

    new_linked_heading = f"# {_markdown_external_link(title, source)}"
    new_body = body
    if old_source:
        old_linked_heading = f"# {_markdown_external_link(title, old_source)}"
        if old_linked_heading in new_body:
            new_body = new_body.replace(old_linked_heading, new_linked_heading, 1)
        else:
            plain_heading = f"# {title}"
            if plain_heading in new_body:
                new_body = new_body.replace(plain_heading, new_linked_heading, 1)

    path.write_text(new_front_block + new_body, encoding="utf-8")
    return True


def backfill_wiki_sources(*, wiki_dir: Path | None = None) -> list[str]:
    """Repair wiki articles whose source URLs were truncated during sync."""

    root = wiki_dir or WIKI_DIR
    updated: list[str] = []
    for wiki_path, archive_path in parse_status_wiki_archive_map().items():
        if wiki_dir is not None and not str(wiki_path).startswith(str(root)):
            continue

        front_matter, _ = parse_raw_front_matter(wiki_path.read_text(encoding="utf-8"))
        current_source = str(front_matter.get("source", "")).strip()
        if not is_truncated_url(current_source):
            continue

        archive_front, _ = parse_raw_front_matter(archive_path.read_text(encoding="utf-8"))
        archive_source = str(archive_front.get("source", "")).strip()
        if not archive_source or is_truncated_url(archive_source):
            continue

        if update_wiki_source(wiki_path, archive_source):
            updated.append(str(wiki_path.relative_to(ROOT)))

    return updated


def backfill_wiki_source_titles(*, wiki_dir: Path | None = None) -> list[str]:
    """Update existing wiki article H1s to linked titles when source is in front matter."""

    root = wiki_dir or WIKI_DIR
    updated: list[str] = []
    for path in sorted(root.rglob("*.md")):
        if path.name in {"_index.md", "INDEX.md"}:
            continue

        content = path.read_text(encoding="utf-8")
        front_matter, body = parse_raw_front_matter(content)
        title = str(front_matter.get("title", "")).strip()
        source = str(front_matter.get("source", "")).strip()
        if not title or not source:
            continue

        linked_heading = f"# {_markdown_external_link(title, source)}"
        plain_heading = f"# {title}"
        if plain_heading not in body or linked_heading in body:
            continue

        match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
        if not match:
            continue

        new_body = body.replace(plain_heading, linked_heading, 1)
        path.write_text(content[: match.end()] + new_body, encoding="utf-8")
        updated.append(str(path.relative_to(ROOT)))

    return updated


def append_sync_log(message: str) -> None:
    """Append one sync log line to logs/sync.log."""

    SYNC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SYNC_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def log_sync_event(level: str, message: str) -> None:
    """Print and persist a sync log event."""

    line = f"[sync_wiki] {level}: {message}"
    print(line, flush=True)
    append_sync_log(line)


def summarize_sync_results(results: list[CompileResult]) -> int:
    """Print a batch summary and return a non-zero exit code when any file failed."""

    failed = [result for result in results if result.errors]
    created = [result for result in results if result.action == "create_article" and not result.errors]
    skipped = [
        result
        for result in results
        if result.action in {"skip_duplicate", "needs_review"} and not result.errors
    ]

    log_sync_event(
        "SUMMARY",
        (
            f"processed={len(results)} created={len(created)} "
            f"skipped={len(skipped)} failed={len(failed)}"
        ),
    )
    for result in failed:
        log_sync_event(
            "FAILED",
            f"{result.source_file}: {'; '.join(result.errors)}",
        )
    return 1 if failed else 0


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
    parser.add_argument(
        "--provider",
        default=None,
        choices=["mlx", "openai", "fixture"],
        help="LLM provider backend (default: LLM_PROVIDER from .env, usually mlx).",
    )
    parser.add_argument(
        "--backfill-titles",
        action="store_true",
        help="Update existing wiki article titles to markdown links using front matter source URLs.",
    )
    parser.add_argument(
        "--backfill-sources",
        action="store_true",
        help="Repair wiki articles whose source URLs were truncated during sync.",
    )
    args = parser.parse_args()

    configure_paths(
        source=args.source,
        wiki=args.wiki,
        archive=args.archive or str(Path(args.source) / "archive"),
    )

    if args.backfill_titles:
        updated = backfill_wiki_source_titles()
        if not updated:
            print("[sync_wiki] no wiki titles to backfill.")
            return 0
        for rel_path in updated:
            print(f"[sync_wiki] backfilled title: {rel_path}")
        return 0

    if args.backfill_sources:
        updated = backfill_wiki_sources()
        if not updated:
            print("[sync_wiki] no wiki sources to backfill.")
            return 0
        for rel_path in updated:
            print(f"[sync_wiki] backfilled source: {rel_path}")
        return 0

    selected: list[Path] | None = None
    if args.files:
        selected = []
        for item in args.files:
            path = Path(item)
            if not path.is_absolute():
                path = RAW_DIR / path.name if path.parent == Path(".") else ROOT / path
            selected.append(path)

    provider = None if args.provider == "fixture" else build_provider(args.provider)
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

    return summarize_sync_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
