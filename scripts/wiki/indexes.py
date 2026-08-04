#!/usr/bin/env python3
"""Rebuild topic _index.md lists from article topics front matter."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from wiki.common import parse_raw_front_matter
from wiki.sync import WIKI_DIR, configure_paths, repo_root
from wiki.densify import ENTITY_ALIASES
from topic_config import CANONICAL_TOPICS, article_topics_for_path, topic_link

# Capture target + optional display label (common.WIKI_LINK_RE only keeps the target).
LINK_WITH_LABEL_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def article_topics_from_file(path: Path) -> list[str]:
    front_matter, _ = parse_raw_front_matter(path.read_text(encoding="utf-8"))
    raw_topics = front_matter.get("topics")
    if isinstance(raw_topics, list) and raw_topics:
        topics = [str(item).strip() for item in raw_topics if str(item).strip()]
        if topics:
            return topics
    return article_topics_for_path(path.name, path.parent.name)


def article_sort_date(path: Path) -> str:
    """Return YYYY-MM-DD for sorting; undated articles sort last when reverse=True."""
    text = path.read_text(encoding="utf-8")
    front_matter, _ = parse_raw_front_matter(text)
    published = str(front_matter.get("published", front_matter.get("created", ""))).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", published):
        return published[:10]
    stem_date = re.match(r"^(\d{4}-\d{2}-\d{2})", path.stem)
    if stem_date:
        return stem_date.group(1)
    return "0000-00-00"


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


def article_titles_by_link_target(wiki_dir: Path) -> dict[str, tuple[str, str]]:
    """Map wiki link targets to (canonical_target, title)."""

    mapping: dict[str, tuple[str, str]] = {}
    for path in sorted(wiki_dir.rglob("*.md")):
        if path.name in {"_index.md", "INDEX.md"}:
            continue
        rel = path.relative_to(wiki_dir).with_suffix("").as_posix()
        front_matter, _ = parse_raw_front_matter(path.read_text(encoding="utf-8"))
        title = str(front_matter.get("title", "")).strip()
        if not title:
            continue
        mapping[rel] = (rel, title)
        mapping[path.stem] = (rel, title)
    return mapping


def repair_index_line(line: str, titles: dict[str, tuple[str, str]]) -> str:
    match = WIKI_LINK_LABEL_RE.search(line)
    if not match:
        return line

    target = match.group(1).strip()
    resolved = titles.get(target) or titles.get(Path(target).name)
    if not resolved:
        return line

    canonical_target, title = resolved
    fixed_link = f"[[{canonical_target}|{title}]]"
    if match.group(0) == fixed_link:
        return line
    return line.replace(match.group(0), fixed_link, 1)


def repair_recent_articles(root_index: Path, wiki_dir: Path) -> int:
    if not root_index.exists():
        return 0

    titles = article_titles_by_link_target(wiki_dir)
    marker = "## Recent Articles"
    content = root_index.read_text(encoding="utf-8")
    if marker not in content:
        return 0

    before, after = content.split(marker, 1)
    section, tail = (after.split("\n## ", 1) + [""])[:2]
    lines = section.splitlines()
    repaired = 0
    updated_lines: list[str] = []
    for line in lines:
        fixed = repair_index_line(line, titles)
        if fixed != line:
            repaired += 1
        updated_lines.append(fixed)

    new_section = "\n".join(updated_lines)
    new_tail = f"\n## {tail}" if tail else ""
    root_index.write_text(before + marker + new_section + new_tail, encoding="utf-8")
    return repaired


RECENT_ENTRY_RE = re.compile(
    r"^- \[\[[^\]]+\|[^\]]+\]\] \((\d{4}-\d{2}-\d{2})\)(?:\s+.*)?$"
)


def sort_recent_articles(root_index: Path) -> int:
    """Sort INDEX.md Recent Articles by date descending (newest first)."""
    if not root_index.exists():
        return 0

    marker = "## Recent Articles"
    content = root_index.read_text(encoding="utf-8")
    if marker not in content:
        return 0

    before, after = content.split(marker, 1)
    section, tail = (after.split("\n## ", 1) + [""])[:2]
    entries: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if RECENT_ENTRY_RE.match(stripped):
            entries.append(stripped)

    if not entries:
        return 0

    sorted_entries = sorted(
        entries,
        key=lambda line: RECENT_ENTRY_RE.match(line).group(1),  # type: ignore[union-attr]
        reverse=True,
    )
    if sorted_entries == entries:
        return 0

    new_section = "\n" + "\n".join(sorted_entries) + "\n"
    new_tail = f"\n## {tail}" if tail else ""
    root_index.write_text(before.rstrip() + f"\n\n{marker}" + new_section + new_tail, encoding="utf-8")
    return len(sorted_entries)


def rebuild_indexes(wiki_dir: Path) -> None:
    by_topic: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen_line: dict[str, set[str]] = defaultdict(set)

    for topic in CANONICAL_TOPICS:
        topic_dir = wiki_dir / topic
        if not topic_dir.is_dir():
            continue
        for path in sorted(topic_dir.glob("*.md")):
            if path.name == "_index.md":
                continue
            line = topic_index_line(path)
            sort_date = article_sort_date(path)
            for slug in article_topics_from_file(path):
                if line not in seen_line[slug]:
                    seen_line[slug].add(line)
                    by_topic[slug].append((sort_date, line))

    for topic in CANONICAL_TOPICS:
        index_path = wiki_dir / topic / "_index.md"
        if not index_path.exists():
            continue
        content = index_path.read_text(encoding="utf-8")
        dated_lines = sorted(by_topic.get(topic, []), key=lambda item: item[0], reverse=True)
        content = replace_section(content, "相关文章", [line for _, line in dated_lines])
        related = [slug for slug in CANONICAL_TOPICS if slug != topic]
        related_links = [topic_link(slug) for slug in related]
        content = replace_section(content, "相关主题", [f"- {link}" for link in related_links])
        index_path.write_text(content, encoding="utf-8")


KEY_COMPANIES_LINE_RE = re.compile(
    r"^([ \t]*-[ \t]*\*\*关键公司\*\*:[ \t]*)([^\n]*)$",
    re.MULTILINE,
)
# Themes / non-company hubs — skip for 关键公司.
SKIP_COMPANY_HUBS = {
    "ai",
    "ai-tools",
    "ai-infrastructure",
    "fed",
    "visual-effects",
    "visual-narrative",
    "embodied-intelligence",
    "具身智能",
    "usdc",
    "usdt",
    "tether",
}
PERSON_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z.'\-]+){1,3}$")
CORP_TOKEN_RE = re.compile(
    r"\b(Capital|Technologies|Technology|Ventures|Partners|Holdings|Corp|Inc|LLC|"
    r"Group|Bank|Systems|Labs|Motors|Energy|Media|Studio|Studios|Networks|"
    r"Combinator|LinkedIn|OpenAI|Anthropic|Learning|English)\b",
    re.IGNORECASE,
)
# hub slugs like elon-musk / christopher-nolan / te-ping-chen
PERSON_SLUG_RE = re.compile(r"^[a-z]{2,}(?:-[a-z]{2,}){1,3}$")
ORG_SLUG_PARTS = {
    "bbc",
    "imax",
    "ibm",
    "aws",
    "gpt",
    "llm",
    "usa",
    "usd",
    "api",
}
# Bare author/person links often look like "First Last"; company brands usually do not.
BARE_COMPANY_NOISE_RE = re.compile(
    r"(@|\.me\b|University|College|Jr\.|Sr\.|Senator|Congress)",
    re.IGNORECASE,
)


def _hub_slugs(wiki_dir: Path) -> set[str]:
    hubs_dir = wiki_dir / "hubs"
    if not hubs_dir.is_dir():
        return set()
    return {path.stem for path in hubs_dir.glob("*.md")}


def _alias_to_entity() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for slug, aliases in ENTITY_ALIASES.items():
        if slug in SKIP_COMPANY_HUBS:
            continue
        mapping[slug.lower()] = slug
        for alias in aliases:
            mapping[alias.lower()] = slug
    return mapping


def _slugify_entity(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or name.lower()


def _company_display(slug: str, *, display_cache: dict[str, str] | None = None) -> str:
    if display_cache and slug in display_cache:
        return display_cache[slug]
    aliases = ENTITY_ALIASES.get(slug)
    if aliases:
        return aliases[0]
    return slug.replace("-", " ").title()


def _is_article_path(path: Path) -> bool:
    return (
        path.suffix == ".md"
        and path.name not in {"_index.md", "INDEX.md", "articles.md"}
        and "hubs" not in path.parts
    )


def _looks_like_person_slug(entity_slug: str) -> bool:
    slug = entity_slug.lower()
    if not PERSON_SLUG_RE.match(slug):
        return False
    parts = slug.split("-")
    if any(part in ORG_SLUG_PARTS for part in parts):
        return False
    slug_words = " ".join(parts)
    if CORP_TOKEN_RE.search(slug_words):
        return False
    return True


def _is_person_like(display: str, entity_slug: str, *, hub_slugs: set[str]) -> bool:
    if entity_slug in ENTITY_ALIASES or entity_slug in hub_slugs:
        return False
    slug_words = entity_slug.replace("_", "-").replace("-", " ")
    if CORP_TOKEN_RE.search(display) or CORP_TOKEN_RE.search(slug_words):
        return False
    if PERSON_NAME_RE.match(display):
        return True
    # Chinese/other labels on person hubs: fall back to slug shape.
    return _looks_like_person_slug(entity_slug)


def collect_topic_company_counts(
    wiki_dir: Path,
    topic: str,
    *,
    hub_slugs: set[str],
    alias_map: dict[str, str],
    display_cache: dict[str, str],
) -> Counter[str]:
    """Count company entities mentioned in articles tagged with this topic."""
    hub_counts: Counter[str] = Counter()
    bare_counts: Counter[str] = Counter()
    for path in wiki_dir.rglob("*.md"):
        if not _is_article_path(path):
            continue
        topics = article_topics_from_file(path)
        # Primary topic folder still counts even if front matter is incomplete.
        if topic not in topics and path.parent.name != topic:
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_WITH_LABEL_RE.finditer(text):
            target = match.group(1).strip()
            label = (match.group(2) or "").strip()
            entity_slug: str | None = None
            from_hub = False
            if target.startswith("hubs/"):
                candidate = target.split("/", 1)[1].strip()
                if not candidate:
                    continue
                from_hub = True
                # Normalize ASCII hub slugs so Anthropic / anthropic merge.
                if re.fullmatch(r"[A-Za-z0-9\-]+", candidate):
                    entity_slug = candidate.lower()
                else:
                    entity_slug = candidate
            elif "/" not in target:
                entity_slug = alias_map.get(target.lower())
                if entity_slug is None and target.lower() in hub_slugs:
                    entity_slug = target.lower()
                elif entity_slug is None:
                    if BARE_COMPANY_NOISE_RE.search(target):
                        continue
                    if PERSON_NAME_RE.match(target):
                        continue
                    # Brand-like bare links: OpenAI, Citadel, Y Combinator, H&M
                    if len(target) < 2 or len(target) > 40:
                        continue
                    if target.count("-") >= 3:
                        continue
                    entity_slug = alias_map.get(target.lower()) or _slugify_entity(target)
                    display_cache.setdefault(entity_slug, target)
            else:
                continue

            if not entity_slug or entity_slug.lower() in {s.lower() for s in SKIP_COMPANY_HUBS}:
                continue
            if entity_slug.count("-") >= 4:
                continue
            display = label or display_cache.get(entity_slug) or _company_display(entity_slug)
            if label:
                display_cache.setdefault(entity_slug, label)
            if re.search(r"摄影|for\s+WSJ|https?://|@", display, re.IGNORECASE):
                continue
            if _is_person_like(display, entity_slug, hub_slugs=hub_slugs):
                continue
            if from_hub:
                hub_counts[entity_slug] += 1
            else:
                bare_counts[entity_slug] += 1

    counts: Counter[str] = Counter()
    counts.update(hub_counts)
    for slug, n in bare_counts.items():
        # Keep known entities always; other bare brands need repetition.
        if slug in hub_slugs or slug in ENTITY_ALIASES or n >= 2 or slug in hub_counts:
            counts[slug] += n
    return counts


def format_key_companies(
    slugs: list[str],
    *,
    hub_slugs: set[str],
    display_cache: dict[str, str],
) -> str:
    parts: list[str] = []
    for slug in slugs:
        display = _company_display(slug, display_cache=display_cache)
        if slug in hub_slugs:
            parts.append(f"[[hubs/{slug}|{display}]]")
        else:
            parts.append(f"[[{display}]]")
    return ", ".join(parts)


def backfill_key_companies(
    wiki_dir: Path,
    *,
    force: bool = False,
    limit: int = 5,
) -> dict[str, list[str]]:
    """Fill empty 关键公司 lines from companies linked in that topic's articles."""
    hub_slugs = _hub_slugs(wiki_dir)
    alias_map = _alias_to_entity()
    updated: dict[str, list[str]] = {}

    for topic in CANONICAL_TOPICS:
        index_path = wiki_dir / topic / "_index.md"
        if not index_path.exists():
            continue
        content = index_path.read_text(encoding="utf-8")
        match = KEY_COMPANIES_LINE_RE.search(content)
        if not match:
            continue
        existing = match.group(2).strip()
        if existing and not force:
            continue

        display_cache: dict[str, str] = {}
        counts = collect_topic_company_counts(
            wiki_dir,
            topic,
            hub_slugs=hub_slugs,
            alias_map=alias_map,
            display_cache=display_cache,
        )
        if not counts:
            continue
        top = [slug for slug, _ in counts.most_common(limit)]
        rendered = format_key_companies(
            top,
            hub_slugs=hub_slugs,
            display_cache=display_cache,
        )
        new_line = f"{match.group(1)}{rendered}"
        content = KEY_COMPANIES_LINE_RE.sub(new_line, content, count=1)
        index_path.write_text(content, encoding="utf-8")
        updated[topic] = top

    return updated


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
    parser.add_argument(
        "--repair-index-labels",
        action="store_true",
        help="Align index wiki-link display labels with article titles",
    )
    parser.add_argument(
        "--backfill-companies",
        action="store_true",
        help="Fill empty 关键公司 from companies linked in each topic's articles",
    )
    parser.add_argument(
        "--force-companies",
        action="store_true",
        help="Overwrite existing 关键公司 when used with --backfill-companies",
    )
    parser.add_argument(
        "--company-limit",
        type=int,
        default=5,
        help="Max companies per topic when backfilling (default: 5)",
    )
    args = parser.parse_args()

    configure_paths(wiki=args.wiki)
    wiki_dir = WIKI_DIR
    root = repo_root()
    if args.repair:
        count = repair_all_front_matter(wiki_dir)
        print(f"Repaired front matter in {count} article(s)")
    if args.repair_index_labels:
        root_index = wiki_dir / "INDEX.md"
        repaired_recent = repair_recent_articles(root_index, wiki_dir)
        print(f"Repaired {repaired_recent} recent-entry label(s) in {root_index}")
    if args.annotate:
        annotate_article_topics(wiki_dir)
    rebuild_indexes(wiki_dir)
    print(f"Rebuilt topic indexes under {wiki_dir}")
    sorted_count = sort_recent_articles(wiki_dir / "INDEX.md")
    if sorted_count:
        print(f"Sorted {sorted_count} recent article(s) in INDEX.md (newest first)")
    if args.backfill_companies:
        updated = backfill_key_companies(
            wiki_dir,
            force=args.force_companies,
            limit=max(1, args.company_limit),
        )
        if updated:
            for topic, companies in updated.items():
                print(f"  {topic}: {', '.join(companies)}")
            print(f"Backfilled 关键公司 for {len(updated)} topic(s)")
        else:
            print("No empty 关键公司 rows needed backfill (or no company links found)")


if __name__ == "__main__":
    main()
