"""Deterministic raw -> wiki sync harness for dev.news-wiki."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_provider import LLMProvider, LLMRequest, build_provider, default_provider, proposal_from_provider
from topic_config import (
    CANONICAL_TOPICS,
    enforce_canonical_topics,
    is_canonical_topic,
    render_canonical_topics_for_prompt,
    topic_hint_from_front_matter,
)
from wiki.common import (
    add_dry_run_arg,
    add_llm_provider_arg,
    load_agents_contract,
    markdown_external_link,
    parse_raw_front_matter,
    relative_prefix,
    reject_fixture_provider,
    repo_root,
    require_mapping,
    resolve_path,
    sanitize_slug,
    slug_fallback_from_raw,
    SLUG_RE,
    normalize_wiki_link_label,
    validate_slug,
    validate_synthesis_labels,
    yaml_quote,
)
from wiki.review import (
    infer_review_labels,
    is_raw_marked_for_review,
    is_review_queue_file,
    mark_raw_needs_review,
    rebuild_review_queue,
)
from wiki.io import (
    append_status_row as _append_status_row,
    article_source_url,
    build_status_row,
    ensure_topic_index as _ensure_topic_index,
    ensure_topic_index_for_slug as _ensure_topic_index_for_slug,
    is_truncated_url,
    list_topic_context,
    parse_status_wiki_archive_map,
    remove_raw_source as _remove_raw_source,
    render_archive_stub,
    render_article_markdown,
    update_indexes as _update_indexes,
)

ROOT = repo_root()
DEFAULT_SOURCE = "newswiki/raw"
DEFAULT_WIKI = "newswiki/wiki"

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


def append_status_row(status_row: str) -> None:
    _append_status_row(STATUS_PATH, status_row)


def ensure_topic_index_for_slug(slug: str, *, title: str = "", rationale: str = "") -> Path:
    return _ensure_topic_index_for_slug(WIKI_DIR, slug, title=title, rationale=rationale)


def ensure_topic_index(proposal: dict[str, Any]) -> Path:
    return _ensure_topic_index(proposal, wiki_dir=WIKI_DIR)


def update_indexes(proposal: dict[str, Any]) -> None:
    _update_indexes(proposal, wiki_dir=WIKI_DIR, root_index=ROOT_INDEX)


def remove_raw_source(raw_path: Path) -> None:
    _remove_raw_source(raw_path, RESOURCES_DIR)


def configure_paths(
    *,
    root: Path | None = None,
    source: Path | str | None = None,
    wiki: Path | str | None = None,
    archive: Path | str | None = None,
    resources: Path | str | None = None,
) -> None:
    global ROOT, RAW_DIR, ARCHIVE_DIR, WIKI_DIR, RESOURCES_DIR, CACHE_PATH, STATUS_PATH, ROOT_INDEX
    global SOURCE_PREFIX, WIKI_PREFIX, SYNC_LOG_PATH

    if root is not None:
        ROOT = root.resolve()

    if source is not None:
        RAW_DIR = resolve_path(ROOT, source)
    if wiki is not None:
        WIKI_DIR = resolve_path(ROOT, wiki)
    if archive is not None:
        ARCHIVE_DIR = resolve_path(ROOT, archive)
    elif source is not None:
        ARCHIVE_DIR = RAW_DIR / "archive"

    if resources is not None:
        RESOURCES_DIR = resolve_path(ROOT, resources)
    elif source is not None:
        RESOURCES_DIR = RAW_DIR.parent / "_resources"

    CACHE_PATH = ARCHIVE_DIR / ".sync_cache.json"
    STATUS_PATH = ARCHIVE_DIR / "STATUS.md"
    ROOT_INDEX = WIKI_DIR / "INDEX.md"
    SOURCE_PREFIX = relative_prefix(ROOT, RAW_DIR)
    WIKI_PREFIX = relative_prefix(ROOT, WIKI_DIR)
    SYNC_LOG_PATH = ROOT / "logs" / "sync.log"


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


def scan_pending_files(
    *,
    include_cached: bool = False,
    include_review: bool = False,
) -> list[Path]:
    cache = load_cache()
    pending: list[Path] = []
    for path in sorted(RAW_DIR.glob("*.md")):
        if is_review_queue_file(path):
            continue
        if not include_review and is_raw_marked_for_review(path):
            continue
        rel = path.name
        if include_cached or cache.get(rel) != _file_hash(path):
            pending.append(path)
    return pending


def build_compile_prompt(raw_path: Path) -> LLMRequest:
    content = raw_path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(content)
    rel = f"{SOURCE_PREFIX}/{raw_path.name}"
    hint = topic_hint_from_front_matter(front_matter)
    hint_block = f"\n{hint}\n" if hint else ""
    prompt = f"""Compile this raw source into one JSON proposal following the contract in AGENTS.md.

Source file: {rel}

Canonical topics (pick exactly one as primary; add canonical secondaries only when cross-cutting):
{render_canonical_topics_for_prompt()}

Do not invent new topic slugs. If none fit well, return action "needs_review" with rationale.

article.slug must be lowercase ASCII only (a-z, 0-9, hyphens). Use a descriptive English slug even when the title is Chinese or mixed script.
Preserve the source article language throughout: article.title, front_matter, section headings, bullets, and key_takeaways must match the raw language. Do not translate or rename titles.

Wiki topic folders on disk:
{list_topic_context(WIKI_DIR) or "- none"}
{hint_block}
Raw front matter:
{json.dumps(front_matter, ensure_ascii=False, indent=2)}

Raw body:
---
{body.strip()}
---
"""
    return LLMRequest(system=load_agents_contract(), prompt=prompt)


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

    topic = require_mapping(proposal, "topic")
    article = require_mapping(proposal, "article")
    index_updates = require_mapping(proposal, "index_updates")
    archive = require_mapping(proposal, "archive")

    validate_slug(str(topic.get("slug", "")), "topic")
    validate_slug(str(article.get("slug", "")), "article")

    topic_slug = str(topic["slug"])
    if not is_canonical_topic(topic_slug):
        raise ValueError(
            f"topic.slug must be one of {list(CANONICAL_TOPICS)}, got '{topic_slug}'."
        )

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
        validate_synthesis_labels([str(b) for b in bullets], "section bullet")

    key_takeaways = article.get("key_takeaways", [])
    if not isinstance(key_takeaways, list) or not key_takeaways:
        raise ValueError("article.key_takeaways must be a non-empty list.")
    validate_synthesis_labels([str(k) for k in key_takeaways], "key takeaway")

    for key in ("topic_index_entry", "root_recent_entry"):
        if not str(index_updates.get(key, "")).strip():
            raise ValueError(f"index_updates.{key} is required.")

    topics = article.get("topics")
    if topics is not None:
        if not isinstance(topics, list) or not topics:
            raise ValueError("article.topics must be a non-empty list when provided.")
        for slug in topics:
            validate_slug(str(slug), "article.topics")
            if not is_canonical_topic(str(slug)):
                raise ValueError(
                    f"article.topics must use canonical slugs {list(CANONICAL_TOPICS)}, "
                    f"got '{slug}'."
                )
        if str(topics[0]) != str(topic["slug"]):
            raise ValueError("article.topics[0] must match topic.slug (primary topic).")

    if archive.get("should_archive") is not True:
        raise ValueError("archive.should_archive must be true for create_article.")
    if not str(front_matter.get("source", "")).strip():
        raise ValueError("article.front_matter.source is required for create_article.")


def normalize_proposal_language(proposal: dict[str, Any], raw_path: Path) -> list[str]:
    if proposal.get("action") != "create_article":
        return []

    content = raw_path.read_text(encoding="utf-8")
    raw_front_matter, _ = parse_raw_front_matter(content)
    raw_title = str(raw_front_matter.get("title", "")).strip()
    if not raw_title:
        return []

    article = require_mapping(proposal, "article")
    front_matter = article.setdefault("front_matter", {})
    notes: list[str] = []

    current_title = str(article.get("title", "")).strip()
    if current_title and current_title != raw_title:
        notes.append(f"Reset article.title to source title: {raw_title!r}.")
    article["title"] = raw_title
    if str(front_matter.get("title", "")).strip() != raw_title:
        front_matter["title"] = raw_title

    raw_description = str(raw_front_matter.get("description", "")).strip()
    if raw_description:
        front_matter["description"] = raw_description

    index_updates = proposal.get("index_updates")
    if isinstance(index_updates, dict):
        for key in ("topic_index_entry", "root_recent_entry"):
            entry = str(index_updates.get(key, "")).strip()
            if not entry:
                continue
            fixed = normalize_wiki_link_label(entry, raw_title)
            if fixed != entry:
                notes.append(f"Reset index_updates.{key} display to source title.")
                index_updates[key] = fixed

    if notes:
        review_notes = proposal.setdefault("review_notes", [])
        if isinstance(review_notes, list):
            review_notes.extend(notes)
    return notes


def normalize_proposal_slugs(proposal: dict[str, Any], raw_path: Path) -> list[str]:
    if proposal.get("action") != "create_article":
        return []

    article = require_mapping(proposal, "article")
    topic = require_mapping(proposal, "topic")
    raw_slug = str(article.get("slug", "")).strip()
    if raw_slug and SLUG_RE.fullmatch(raw_slug):
        return []

    fallback = slug_fallback_from_raw(raw_path)
    new_slug = sanitize_slug(raw_slug, fallback=fallback)
    if not new_slug:
        new_slug = fallback

    notes = [f"Normalized invalid article slug '{raw_slug}' -> '{new_slug}'."]
    old_slug = raw_slug
    article["slug"] = new_slug

    topic_slug = str(topic.get("slug", "")).strip()
    article_path = str(article.get("path", "")).strip()
    if article_path and old_slug in article_path:
        article["path"] = article_path.replace(old_slug, new_slug)
    elif topic_slug:
        article["path"] = f"{WIKI_PREFIX}/{topic_slug}/{new_slug}.md"

    index_updates = proposal.get("index_updates")
    if isinstance(index_updates, dict):
        for key in ("topic_index_entry", "root_recent_entry"):
            entry = str(index_updates.get(key, ""))
            if old_slug and old_slug in entry:
                index_updates[key] = entry.replace(old_slug, new_slug)

    review_notes = proposal.setdefault("review_notes", [])
    if isinstance(review_notes, list):
        review_notes.extend(notes)
    return notes


def normalize_wiki_path(path: str, *, topic_slug: str = "") -> str:
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
    if proposal.get("action") != "create_article":
        return

    topic = require_mapping(proposal, "topic")
    article = require_mapping(proposal, "article")
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
        article["path"] = normalize_wiki_path(f"{topic_slug}/{article_slug}.md", topic_slug=topic_slug)


def normalize_proposal_source(proposal: dict[str, Any], raw_path: Path) -> None:
    source = article_source_url(proposal, raw_path)
    if not source:
        return
    article = require_mapping(proposal, "article")
    front_matter = article.setdefault("front_matter", {})
    front_matter["source"] = source


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
    proposal = enforce_canonical_topics(proposal)
    normalize_proposal_language(proposal, raw_path)
    normalize_proposal_slugs(proposal, raw_path)
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
        if action == "needs_review" and not dry_run:
            proposed_topic = str(proposal.get("proposed_topic", "")).strip()
            mark_raw_needs_review(
                raw_path,
                labels=infer_review_labels(result.review_notes),
                notes=result.review_notes,
                proposed_topic=proposed_topic,
            )
            queue_path = rebuild_review_queue(RAW_DIR)
            if queue_path:
                result.review_notes.append(f"Review queue updated: {queue_path.relative_to(ROOT)}")
        return result

    normalize_proposal_source(proposal, raw_path)

    article = require_mapping(proposal, "article")
    article_path = ROOT / str(article["path"])
    result.article_path = str(article_path.relative_to(ROOT))

    if dry_run:
        return result

    article_path.parent.mkdir(parents=True, exist_ok=True)
    article_path.write_text(render_article_markdown(proposal), encoding="utf-8")
    update_indexes(proposal)

    archive = require_mapping(proposal, "archive")
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
    include_review: bool = False,
) -> list[CompileResult]:
    targets = files or scan_pending_files(
        include_cached=include_cached,
        include_review=include_review,
    )
    if not targets:
        return []

    llm = provider or build_provider(default_provider())
    results: list[CompileResult] = []
    for raw_path in targets:
        log_sync_event("START", raw_path.name)
        result = sync_file(raw_path, llm, dry_run=dry_run, no_archive=no_archive)
        results.append(result)
        if result.errors:
            log_sync_event("ERROR", f"{raw_path.name}: {'; '.join(result.errors)} (continuing)")
        else:
            print(f"[sync_wiki] {_format_result(result)}", flush=True)
            append_sync_log(f"[sync_wiki] {_format_result(result)}")
    return results


compile_file = sync_file
run_compile = run_sync


def update_wiki_source(path: Path, source: str) -> bool:
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
        f"source: {yaml_quote(source)}",
        front_block,
        count=1,
        flags=re.MULTILINE,
    )

    new_linked_heading = f"# {markdown_external_link(title, source)}"
    new_body = body
    if old_source:
        old_linked_heading = f"# {markdown_external_link(title, old_source)}"
        if old_linked_heading in new_body:
            new_body = new_body.replace(old_linked_heading, new_linked_heading, 1)
        else:
            plain_heading = f"# {title}"
            if plain_heading in new_body:
                new_body = new_body.replace(plain_heading, new_linked_heading, 1)

    path.write_text(new_front_block + new_body, encoding="utf-8")
    return True


def backfill_wiki_sources(*, wiki_dir: Path | None = None) -> list[str]:
    root = wiki_dir or WIKI_DIR
    updated: list[str] = []
    for wiki_path, archive_path in parse_status_wiki_archive_map(
        root=ROOT,
        status_path=STATUS_PATH,
        archive_dir=ARCHIVE_DIR,
    ).items():
        if wiki_dir is not None and not str(wiki_path).startswith(str(root)):
            continue

        front_matter, _ = parse_raw_front_matter(wiki_path.read_text(encoding="utf-8"))
        current_source = str(front_matter.get("source", "")).strip()
        if not is_truncated_url(current_source):
            continue

        archive_front, _ = parse_raw_front_matter(archive_path.read_text(encoding="utf-8"))
        archive_source_url = str(archive_front.get("source", "")).strip()
        if not archive_source_url or is_truncated_url(archive_source_url):
            continue

        if update_wiki_source(wiki_path, archive_source_url):
            updated.append(str(wiki_path.relative_to(ROOT)))

    return updated


def backfill_wiki_source_titles(*, wiki_dir: Path | None = None) -> list[str]:
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

        linked_heading = f"# {markdown_external_link(title, source)}"
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
    SYNC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SYNC_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def log_sync_event(level: str, message: str) -> None:
    line = f"[sync_wiki] {level}: {message}"
    print(line, flush=True)
    append_sync_log(line)


def summarize_sync_results(results: list[CompileResult]) -> int:
    failed = [result for result in results if result.errors]
    created = [result for result in results if result.action == "create_article" and not result.errors]
    skipped = [
        result
        for result in results
        if result.action in {"skip_duplicate", "needs_review"} and not result.errors
    ]

    log_sync_event(
        "SUMMARY",
        f"processed={len(results)} created={len(created)} skipped={len(skipped)} failed={len(failed)}",
    )
    for result in failed:
        log_sync_event("FAILED", f"{result.source_file}: {'; '.join(result.errors)}")
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
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Process raw files already labeled sync_status: needs_review.",
    )
    add_dry_run_arg(parser)
    parser.add_argument("--no-archive", action="store_true", help="Write wiki output but keep raw files in place.")
    add_llm_provider_arg(parser)
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

    if reject_fixture_provider(args.provider, script="sync_wiki"):
        return 1

    selected: list[Path] | None = None
    if args.files:
        selected = []
        for item in args.files:
            path = Path(item)
            if not path.is_absolute():
                path = RAW_DIR / path.name if path.parent == Path(".") else ROOT / path
            selected.append(path)

    provider = build_provider(args.provider)
    results = run_sync(
        files=selected,
        provider=provider,
        dry_run=args.dry_run,
        no_archive=args.no_archive,
        include_cached=args.all,
        include_review=args.include_review,
    )
    if not results:
        print("[sync_wiki] nothing to sync.")
        return 0

    return summarize_sync_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
