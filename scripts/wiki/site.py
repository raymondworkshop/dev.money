import argparse
import re
import shutil
from pathlib import Path

from wiki.common import repo_root, resolve_path as wiki_resolve_path


ROOT = repo_root()
RECENT_ARTICLES_MARKER = "## Recent Articles"
TOPICS_MARKER = "## Topics"
RELATED_ARTICLES_MARKER = "## 相关文章"
RECENT_ARTICLES_LIMIT = 5
TOPICS_DISPLAY_LIMIT = 6
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
PROTECTED_RE = re.compile(
    r"\[\[[^\]]+\]\]|\[[^\]]+\]\([^)]+\)|https?://[^\s)>\]]+"
)
ARTICLE_ENTRY_RE = re.compile(r"^- \[\[[^\]]+\|[^\]]+\]\] \(\d{4}-\d{2}-\d{2}\)$")
MORE_ARTICLES_ENTRY = "- [[articles|More]]"


def has_front_matter(content: str) -> bool:
    return content.startswith("---\n")


def add_front_matter(content: str, fields: dict[str, str]) -> str:
    if has_front_matter(content):
        return content
    front_matter = "\n".join(f'{key}: "{value}"' for key, value in fields.items())
    return f"---\n{front_matter}\n---\n\n{content}"


def normalize_quartz_links(content: str) -> str:
    """Point Obsidian-style folder index links at Quartz folder pages."""
    content = re.sub(r"\[\[([^|\]]+)/_index\|", r"[[\1|", content)
    content = re.sub(r"\[\[([^|\]]+)/_index\]\]", r"[[\1]]", content)
    return content


def _is_list_entry(line: str) -> bool:
    stripped = line.strip()
    if stripped == MORE_ARTICLES_ENTRY:
        return False
    return stripped.startswith("- [[") and "|" in stripped


def _is_article_entry(line: str) -> bool:
    return bool(ARTICLE_ENTRY_RE.match(line.strip()))


def _collect_list_entries(lines: list[str]) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = line.strip()
        if not _is_list_entry(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        entries.append(normalized)
    return entries


def _collect_article_entries_from_text(content: str) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()
    for line in content.splitlines():
        normalized = line.strip()
        if not _is_article_entry(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        entries.append(normalized)
    return entries


def _collect_recent_article_entries(content: str) -> list[str]:
    if RECENT_ARTICLES_MARKER not in content:
        return []
    _, after = content.split(RECENT_ARTICLES_MARKER, 1)
    section_lines: list[str] = []
    for line in after.splitlines():
        if line.strip().startswith("## "):
            break
        section_lines.append(line)
    return _collect_article_entries_from_text("\n".join(section_lines))


def _render_trimmed_entries(entries: list[str], *, limit: int = RECENT_ARTICLES_LIMIT) -> str:
    block_lines = list(entries[:limit])
    if len(entries) > limit:
        block_lines.append(MORE_ARTICLES_ENTRY)
    return "\n".join(block_lines)


def _replace_section_block(
    content: str,
    marker: str,
    block: str,
    *,
    stop_prefix: str = "## ",
) -> str:
    if marker not in content:
        return content

    before, after = content.split(marker, 1)
    after_lines = after.splitlines()
    rest_start = len(after_lines)
    for index, line in enumerate(after_lines):
        if line.strip().startswith(stop_prefix):
            rest_start = index
            break

    rest = "\n".join(after_lines[rest_start:]).lstrip("\n")
    updated = before.rstrip() + f"\n\n{marker}\n\n{block}\n"
    if rest:
        updated += f"\n{rest}"
    if not updated.endswith("\n"):
        updated += "\n"
    return updated


def trim_marked_list_section(
    content: str,
    marker: str,
    *,
    limit: int = RECENT_ARTICLES_LIMIT,
    stop_prefix: str = "## ",
) -> tuple[str, list[str]]:
    if marker not in content:
        return content, []

    _, after = content.split(marker, 1)
    after_lines = after.splitlines()
    rest_start = len(after_lines)
    for index, line in enumerate(after_lines):
        if line.strip().startswith(stop_prefix):
            rest_start = index
            break

    entries = _collect_list_entries(after_lines[:rest_start])
    block = _render_trimmed_entries(entries, limit=limit)
    return _replace_section_block(content, marker, block, stop_prefix=stop_prefix), entries


def trim_topics_groups_for_site(content: str) -> str:
    if TOPICS_MARKER not in content:
        return content

    before, after = content.split(TOPICS_MARKER, 1)
    after_lines = after.splitlines()
    rest_start = len(after_lines)
    for index, line in enumerate(after_lines):
        if line.strip().startswith("## ") and not line.strip().startswith("### "):
            rest_start = index
            break

    topics_lines = after_lines[:rest_start]
    rest = "\n".join(after_lines[rest_start:]).lstrip("\n")

    rendered: list[str] = []
    current_group: list[str] = []
    for line in topics_lines:
        if line.startswith("### "):
            if current_group:
                rendered.extend(_render_topic_group(current_group, limit=TOPICS_DISPLAY_LIMIT))
            current_group = [line]
            continue
        current_group.append(line)

    if current_group:
        rendered.extend(_render_topic_group(current_group, limit=TOPICS_DISPLAY_LIMIT))

    updated = before.rstrip() + f"\n\n{TOPICS_MARKER}\n\n" + "\n".join(rendered).rstrip() + "\n"
    if rest:
        updated += f"\n{rest}"
    if not updated.endswith("\n"):
        updated += "\n"
    return updated


def _render_topic_group(group_lines: list[str], *, limit: int = RECENT_ARTICLES_LIMIT) -> list[str]:
    if not group_lines:
        return []

    heading = group_lines[0]
    body_lines = group_lines[1:] if heading.startswith("### ") else group_lines
    entries = _collect_list_entries(body_lines)
    rendered = [heading, ""] if heading.startswith("### ") else []
    if entries:
        rendered.append(_render_trimmed_entries(entries, limit=limit))
    rendered.append("")
    return rendered


def trim_recent_articles_for_site(content: str) -> tuple[str, list[str]]:
    trimmed, entries = trim_marked_list_section(
        content,
        RECENT_ARTICLES_MARKER,
        limit=RECENT_ARTICLES_LIMIT,
    )
    return trimmed, _collect_article_entries_from_text("\n".join(entries))


def trim_related_articles_for_site(content: str) -> str:
    trimmed, _ = trim_marked_list_section(
        content,
        RELATED_ARTICLES_MARKER,
        limit=RECENT_ARTICLES_LIMIT,
    )
    return trimmed


def write_all_articles_page(content_dir: Path, entries: list[str]) -> None:
    if not entries:
        return
    page_path = content_dir / "articles.md"
    body = "\n".join(entries)
    page_path.write_text(f"# All Articles\n\n{body}\n", encoding="utf-8")


def resolve_path(value: str) -> Path:
    return wiki_resolve_path(ROOT, value)


def _converter():
    import opencc

    return opencc.OpenCC("s2t")


def to_traditional(text: str) -> str:
    if not text:
        return text
    return _converter().convert(text)


def _convert_wiki_link(match: re.Match[str]) -> str:
    path = match.group(1)
    display = match.group(2)
    if display is not None:
        return f"[[{path}|{to_traditional(display)}]]"
    return match.group(0)


def _convert_md_link(match: re.Match[str]) -> str:
    label = match.group(1)
    url = match.group(2)
    return f"[{to_traditional(label)}]({url})"


def convert_visible_text(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in PROTECTED_RE.finditer(text):
        if match.start() > last:
            parts.append(to_traditional(text[last : match.start()]))
        token = match.group(0)
        if token.startswith("[["):
            parts.append(WIKI_LINK_RE.sub(_convert_wiki_link, token))
        elif token.startswith("["):
            parts.append(MD_LINK_RE.sub(_convert_md_link, token))
        else:
            parts.append(token)
        last = match.end()
    if last < len(text):
        parts.append(to_traditional(text[last:]))
    return "".join(parts)


def convert_front_matter_line(line: str) -> str:
    if re.match(r'^source:\s*"?https?://', line.strip()):
        return line
    return convert_visible_text(line)


def convert_markdown(content: str) -> str:
    if not content.startswith("---\n"):
        return convert_visible_text(content)

    end = content.find("\n---\n", 4)
    if end == -1:
        return convert_visible_text(content)

    front_matter = content[4:end]
    body = content[end + 5 :]
    converted_front = "\n".join(convert_front_matter_line(line) for line in front_matter.splitlines())
    return f"---\n{converted_front}\n---\n{convert_visible_text(body)}"


def prepare_content(
    wiki_dir: Path,
    content_dir: Path,
    *,
    traditional_chinese: bool = True,
) -> None:
    if not wiki_dir.exists():
        raise FileNotFoundError(f"Wiki directory not found: {wiki_dir}")

    if content_dir.exists():
        shutil.rmtree(content_dir)
    content_dir.mkdir(parents=True, exist_ok=True)

    all_article_entries: list[str] = []
    for source in wiki_dir.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(wiki_dir)
        if rel.parts and rel.parts[0].startswith("."):
            continue
        if source.name == "articles.md":
            continue
        if source.name == "INDEX.md":
            target = content_dir / "index.md"
        elif source.name == "_index.md":
            target = content_dir / rel.parent / "index.md"
        else:
            target = content_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() == ".md":
            content = source.read_text(encoding="utf-8")
            content = normalize_quartz_links(content)
            if source.name == "INDEX.md":
                content = trim_topics_groups_for_site(content)
                content, all_article_entries = trim_recent_articles_for_site(content)
                content = add_front_matter(
                    content,
                    {
                        "title": "News Wiki",
                        "created": "2026-05-30",
                    },
                )
            elif source.name == "_index.md":
                content = trim_related_articles_for_site(content)
            if traditional_chinese:
                content = convert_markdown(content)
            target.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(source, target)

    write_all_articles_page(content_dir, all_article_entries)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy curated business wiki content into the Quartz content folder."
    )
    parser.add_argument("--wiki", default="newswiki/wiki", help="Source wiki directory")
    parser.add_argument(
        "--content", default="site/content", help="Destination Quartz content directory"
    )
    parser.add_argument(
        "--traditional-chinese",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Convert simplified Chinese to traditional for site output (default: on)",
    )
    args = parser.parse_args()

    wiki_dir = resolve_path(args.wiki)
    content_dir = resolve_path(args.content)
    prepare_content(
        wiki_dir,
        content_dir,
        traditional_chinese=args.traditional_chinese,
    )
    print(f"Prepared Quartz content: {wiki_dir} -> {content_dir}")


if __name__ == "__main__":
    main()
