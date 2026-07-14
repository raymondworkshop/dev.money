"""Wiki index updates, archive stubs, resource cleanup, and article rendering."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from topic_config import TOPIC_LABELS, topic_link

from wiki.common import (
    RESOURCE_DIR_RE,
    TRUNCATED_URL_RE,
    WIKI_PATH_RE,
    article_language,
    markdown_external_link,
    parse_raw_front_matter,
    require_mapping,
    takeaways_heading,
    topic_footer_labels,
    yaml_quote,
)

# --- indexes ---


def append_unique_line(path: Path, section_heading: str, line: str) -> None:
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


def prepend_recent_article(root_index: Path, entry: str) -> None:
    content = root_index.read_text(encoding="utf-8")
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
    root_index.write_text(updated, encoding="utf-8")


def ensure_topic_index_for_slug(
    wiki_dir: Path,
    slug: str,
    *,
    title: str = "",
    rationale: str = "",
) -> Path:
    topic_dir = wiki_dir / slug
    topic_dir.mkdir(parents=True, exist_ok=True)
    index_path = topic_dir / "_index.md"
    if index_path.exists():
        return index_path

    display = title or TOPIC_LABELS.get(slug, slug.replace("-", " ").title())
    overview = rationale or f"{display} related articles and investment notes."
    stub = f"""# {display}

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


def article_topic_slugs(proposal: dict[str, Any]) -> list[str]:
    topic = require_mapping(proposal, "topic")
    article = require_mapping(proposal, "article")
    topics = article.get("topics")
    if isinstance(topics, list) and topics:
        return [str(slug) for slug in topics]
    return [str(topic["slug"])]


def update_indexes(proposal: dict[str, Any], *, wiki_dir: Path, root_index: Path) -> None:
    index_updates = require_mapping(proposal, "index_updates")
    entry = str(index_updates["topic_index_entry"]).strip()
    for slug in article_topic_slugs(proposal):
        topic_index = ensure_topic_index_for_slug(wiki_dir, slug)
        append_unique_line(topic_index, "相关文章", entry)
    prepend_recent_article(root_index, str(index_updates["root_recent_entry"]).strip())


def ensure_topic_index(proposal: dict[str, Any], *, wiki_dir: Path) -> Path:
    topic = require_mapping(proposal, "topic")
    return ensure_topic_index_for_slug(
        wiki_dir,
        str(topic["slug"]),
        title=str(topic.get("title", topic["slug"])),
        rationale=str(topic.get("rationale", "")).strip(),
    )


def list_topic_context(wiki_dir: Path) -> str:
    lines: list[str] = []
    for topic_dir in sorted(wiki_dir.iterdir()):
        if not topic_dir.is_dir():
            continue
        index_path = topic_dir / "_index.md"
        if index_path.exists():
            first_line = index_path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            lines.append(f"- {topic_dir.name}: {first_line}")
    return "\n".join(lines)


# --- archive ---


def is_truncated_url(url: str) -> bool:
    return bool(TRUNCATED_URL_RE.search(url.strip()))


def raw_source_url(raw_path: Path) -> str:
    if not raw_path.exists():
        return ""
    raw_front, _ = parse_raw_front_matter(raw_path.read_text(encoding="utf-8"))
    return str(raw_front.get("source", "")).strip()


def article_source_url(proposal: dict[str, Any], raw_path: Path | None = None) -> str:
    article = require_mapping(proposal, "article")
    front_matter = article.get("front_matter", {})
    proposal_source = str(front_matter.get("source", "")).strip()

    if raw_path is not None:
        raw_source = raw_source_url(raw_path)
        if raw_source:
            return raw_source

    return proposal_source


def build_status_row(proposal: dict[str, Any], raw_path: Path) -> str:
    topic = require_mapping(proposal, "topic")
    article = require_mapping(proposal, "article")
    topic_title = str(topic.get("title", topic["slug"])).strip()
    article_path = str(article.get("path", "")).strip()
    if not article_path:
        raise ValueError("article.path is required for archive status.")
    return f"| {raw_path.name} | {topic_title} | `{article_path}` | Archived |"


def render_archive_stub(proposal: dict[str, Any], raw_path: Path) -> str:
    article = require_mapping(proposal, "article")
    front_matter = article.get("front_matter", {})
    source = article_source_url(proposal, raw_path)
    if not source:
        raise ValueError("article.front_matter.source is required for archive stub.")

    title = str(article.get("title") or front_matter.get("title", raw_path.stem)).strip()
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"source: {yaml_quote(source)}",
    ]
    for key in ("published", "created"):
        if front_matter.get(key):
            lines.append(f"{key}: {yaml_quote(str(front_matter[key]))}")
    lines.extend(
        [
            "---",
            "",
            "Provenance stub. Synced to wiki; full article at `source` above.",
            "",
        ]
    )
    return "\n".join(lines)


def append_status_row(status_path: Path, status_row: str) -> None:
    row = status_row.strip()
    if status_path.exists() and row in status_path.read_text(encoding="utf-8"):
        return

    if status_path.exists():
        content = status_path.read_text(encoding="utf-8")
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

    status_path.write_text(updated, encoding="utf-8")


def normalize_archive_filename(name: str) -> str:
    return (
        name.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def resolve_archive_path(archive_dir: Path, archive_name: str) -> Path | None:
    direct = archive_dir / archive_name
    if direct.exists():
        return direct

    normalized = normalize_archive_filename(archive_name)
    for candidate in archive_dir.glob("*.md"):
        if candidate.name == normalized or normalize_archive_filename(candidate.name) == normalized:
            return candidate
    return None


def parse_status_wiki_archive_map(
    *,
    root: Path,
    status_path: Path,
    archive_dir: Path,
) -> dict[Path, Path]:
    if not status_path.exists():
        return {}

    mapping: dict[Path, Path] = {}
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "Wiki Location" in line or line.startswith("|------"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 3:
            continue

        archive_name = parts[0]
        wiki_match = WIKI_PATH_RE.search(parts[2])
        if not wiki_match:
            continue

        wiki_path = root / wiki_match.group(1)
        archive_path = resolve_archive_path(archive_dir, archive_name)
        if wiki_path.exists() and archive_path is not None:
            mapping[wiki_path] = archive_path
    return mapping


# --- resources ---


def resource_dirs_for_raw(raw_path: Path, resources_dir: Path) -> list[Path]:
    dirs: set[Path] = set()
    if raw_path.exists():
        for match in RESOURCE_DIR_RE.finditer(raw_path.read_text(encoding="utf-8")):
            dirs.add(resources_dir / match.group(1))

    default_dir = resources_dir / raw_path.stem
    if default_dir.exists():
        dirs.add(default_dir)

    return sorted(dirs)


def remove_raw_resources(raw_path: Path, resources_dir: Path) -> list[Path]:
    removed: list[Path] = []
    for resource_dir in resource_dirs_for_raw(raw_path, resources_dir):
        if resource_dir.is_dir():
            shutil.rmtree(resource_dir)
            removed.append(resource_dir)
    return removed


def remove_raw_source(raw_path: Path, resources_dir: Path) -> None:
    remove_raw_resources(raw_path, resources_dir)
    if raw_path.exists():
        raw_path.unlink()


# --- sync_render ---


def format_front_matter(front_matter: dict[str, Any]) -> str:
    lines = ["---"]
    for key in ("title", "source", "published", "created", "description"):
        if key in front_matter and front_matter[key]:
            lines.append(f"{key}: {yaml_quote(str(front_matter[key]))}")

    authors = front_matter.get("author", [])
    if isinstance(authors, str):
        authors = [authors]
    if authors:
        lines.append("author:")
        for author in authors:
            author_text = str(author).strip()
            if not author_text.startswith('"'):
                author_text = yaml_quote(author_text)
            lines.append(f"  - {author_text}")

    topics = front_matter.get("topics", [])
    if isinstance(topics, str):
        topics = [topics]
    if topics:
        lines.append("topics:")
        for slug in topics:
            lines.append(f"  - {str(slug).strip()}")

    lines.append("---")
    return "\n".join(lines)


def render_article_markdown(proposal: dict[str, Any]) -> str:
    article = require_mapping(proposal, "article")
    front_matter = dict(article["front_matter"])
    front_matter["topics"] = article_topic_slugs(proposal)
    title = str(article.get("title") or front_matter.get("title", "")).strip()
    source = str(front_matter.get("source", "")).strip()
    heading = f"# {markdown_external_link(title, source)}" if source else f"# {title}"
    parts = [format_front_matter(front_matter), "", heading, ""]

    for section in article["sections"]:
        section_heading = str(section["heading"]).strip()
        parts.append(f"## {section_heading}")
        for bullet in section["bullets"]:
            parts.append(f"- {str(bullet).strip()}")
        parts.append("")

    lang = article_language(article)
    parts.append(f"## {takeaways_heading(lang)}")
    for takeaway in article["key_takeaways"]:
        parts.append(f"- {str(takeaway).strip()}")
    parts.append("")

    footer = article.get("topic_footer", {})
    topic_links = footer.get("topic_links")
    if isinstance(topic_links, list) and topic_links:
        links = ", ".join(str(link).strip() for link in topic_links if str(link).strip())
    else:
        links = ", ".join(topic_link(slug) for slug in front_matter["topics"])
    tags = footer.get("tags", [])
    tag_line = " ".join(str(tag).strip() for tag in tags if str(tag).strip())
    topics_label, tags_label = topic_footer_labels(lang)
    parts.extend(["---", f"**{topics_label}**: {links}  ", f"**{tags_label}**: {tag_line}"])
    return "\n".join(parts).strip() + "\n"
