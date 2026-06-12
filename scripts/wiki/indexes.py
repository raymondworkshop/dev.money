#!/usr/bin/env python3
"""Rebuild topic _index.md lists from article topics front matter."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from wiki.common import parse_raw_front_matter
from wiki.sync import WIKI_DIR, configure_paths
from topic_config import CANONICAL_TOPICS, article_topics_for_path, topic_link


def article_topics_from_file(path: Path) -> list[str]:
    front_matter, _ = parse_raw_front_matter(path.read_text(encoding="utf-8"))
    raw_topics = front_matter.get("topics")
    if isinstance(raw_topics, list) and raw_topics:
        topics = [str(item).strip() for item in raw_topics if str(item).strip()]
        if topics:
            return topics
    return article_topics_for_path(path.name, path.parent.name)


def topic_index_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(text)
    slug = path.stem
    title = str(front_matter.get("title", "")).strip()
    if not title:
        heading = re.search(r"^# (?:\[([^\]]+)\]\([^)]+\)|(.+))$", body, re.MULTILINE)
        if heading:
            title = (heading.group(1) or heading.group(2) or "").strip()
    if not title:
        title = slug
    published = str(front_matter.get("published", front_matter.get("created", ""))).strip()
    description = str(front_matter.get("description", "")).strip()
    suffix = f" - {description}" if description else ""
    date_suffix = f" ({published})" if published else ""
    return f"- [[{slug}|{title}]]{date_suffix}{suffix}"


CORRUPTED_WIKI_AUTHOR_LINE_RE = re.compile(r'(\]\]")(?:  - [\w-]+)+$')
CORRUPTED_QUOTED_LINE_RE = re.compile(r'(")(?:  - [\w-]+)+$')
MERGED_TOPICS_LINE_RE = re.compile(r'"topics:\s*$')


def repair_front_matter_block(front_block: str) -> str:
    """Fix topic annotation damage inside YAML front matter."""

    repaired: list[str] = []
    for line in front_block.splitlines():
        if MERGED_TOPICS_LINE_RE.search(line):
            line = MERGED_TOPICS_LINE_RE.sub('"', line)
        elif CORRUPTED_WIKI_AUTHOR_LINE_RE.search(line):
            line = CORRUPTED_WIKI_AUTHOR_LINE_RE.sub(r"\1", line)
        elif CORRUPTED_QUOTED_LINE_RE.search(line):
            line = CORRUPTED_QUOTED_LINE_RE.sub(r"\1", line)
        repaired.append(line)
    return "\n".join(repaired)


def strip_topics_blocks(front_block: str) -> str:
    topic_slug_pattern = "|".join(re.escape(slug) for slug in CANONICAL_TOPICS)
    orphan_topic_line_re = re.compile(rf"^  - ({topic_slug_pattern})$")
    lines = repair_front_matter_block(front_block).splitlines()
    cleaned: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == "topics:":
            index += 1
            while index < len(lines) and lines[index].startswith("  - "):
                index += 1
            continue
        if orphan_topic_line_re.match(lines[index]):
            index += 1
            continue
        cleaned.append(lines[index])
        index += 1
    return "\n".join(cleaned).rstrip()


def replace_section(content: str, heading: str, lines: list[str]) -> str:
    marker = f"## {heading}"
    block = "\n".join(lines).rstrip() + "\n" if lines else ""
    if marker not in content:
        return content.rstrip() + f"\n\n{marker}\n{block}"
    before, after = content.split(marker, 1)
    rest = after.split("\n## ", 1)
    tail = f"\n## {rest[1]}" if len(rest) > 1 else ""
    return before.rstrip() + f"\n\n{marker}\n{block}" + tail


def rebuild_indexes(wiki_dir: Path) -> None:
    by_topic: dict[str, list[str]] = defaultdict(list)
    seen_line: dict[str, set[str]] = defaultdict(set)

    for topic in CANONICAL_TOPICS:
        topic_dir = wiki_dir / topic
        if not topic_dir.is_dir():
            continue
        for path in sorted(topic_dir.glob("*.md")):
            if path.name == "_index.md":
                continue
            line = topic_index_line(path)
            for slug in article_topics_from_file(path):
                if line not in seen_line[slug]:
                    seen_line[slug].add(line)
                    by_topic[slug].append(line)

    for topic in CANONICAL_TOPICS:
        index_path = wiki_dir / topic / "_index.md"
        if not index_path.exists():
            continue
        content = index_path.read_text(encoding="utf-8")
        content = replace_section(content, "相关文章", by_topic.get(topic, []))
        related = [slug for slug in CANONICAL_TOPICS if slug != topic]
        related_links = [topic_link(slug) for slug in related]
        content = replace_section(content, "相关主题", [f"- {link}" for link in related_links])
        index_path.write_text(content, encoding="utf-8")


def annotate_article_topics(wiki_dir: Path) -> None:
    topic_re = re.compile(r"\*\*Topics?\*\*:.*")
    for topic in CANONICAL_TOPICS:
        topic_dir = wiki_dir / topic
        if not topic_dir.is_dir():
            continue
        for path in topic_dir.glob("*.md"):
            if path.name == "_index.md":
                continue
            topics = article_topics_for_path(path.name, topic)
            text = path.read_text(encoding="utf-8")
            topic_links = ", ".join(topic_link(slug) for slug in topics)
            footer = f"**Topics**: {topic_links}  "

            if text.startswith("---\n"):
                end = text.find("\n---\n", 4)
                if end == -1:
                    continue
                front_block = text[4:end]
                body = text[end + 5 :]
                front_block = strip_topics_blocks(repair_front_matter_block(front_block))
                front_block += "\ntopics:\n" + "\n".join(f"  - {slug}" for slug in topics)
                text = f"---\n{front_block}\n---\n{body}"
            else:
                text = (
                    "---\n"
                    + "topics:\n"
                    + "\n".join(f"  - {slug}" for slug in topics)
                    + f"\n---\n{text}"
                )

            if topic_re.search(text):
                text = topic_re.sub(footer, text, count=1)
            elif "**Tags**" in text:
                text = text.replace("**Tags**:", f"{footer}\n**Tags**:", 1)
            elif text.rstrip().endswith("---"):
                text = text.rstrip() + f"\n{footer}\n"
            else:
                text = text.rstrip() + f"\n\n---\n{footer}\n"

            path.write_text(text, encoding="utf-8")


def repair_all_front_matter(wiki_dir: Path) -> int:
    repaired = 0
    for topic in CANONICAL_TOPICS:
        topic_dir = wiki_dir / topic
        if not topic_dir.is_dir():
            continue
        for path in topic_dir.glob("*.md"):
            if path.name == "_index.md":
                continue
            if not path.read_text(encoding="utf-8").startswith("---\n"):
                continue
            text = path.read_text(encoding="utf-8")
            end = text.find("\n---\n", 4)
            if end == -1:
                continue
            front_block = text[4:end]
            fixed_block = strip_topics_blocks(front_block)
            topics = article_topics_for_path(path.name, topic)
            fixed_block += "\ntopics:\n" + "\n".join(f"  - {slug}" for slug in topics)
            updated = f"---\n{fixed_block}\n---\n{text[end + 5 :]}"
            if updated != text:
                path.write_text(updated, encoding="utf-8")
                repaired += 1
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild wiki topic indexes from article topics.")
    parser.add_argument("--wiki", default="newswiki/wiki")
    parser.add_argument("--annotate", action="store_true", help="Write topics front matter before rebuild")
    parser.add_argument("--repair", action="store_true", help="Fix corrupted YAML front matter")
    args = parser.parse_args()

    configure_paths(wiki=args.wiki)
    wiki_dir = WIKI_DIR
    if args.repair:
        count = repair_all_front_matter(wiki_dir)
        print(f"Repaired front matter in {count} article(s)")
    if args.annotate:
        annotate_article_topics(wiki_dir)
    rebuild_indexes(wiki_dir)
    print(f"Rebuilt topic indexes under {wiki_dir}")


if __name__ == "__main__":
    main()
