"""Convert simplified Chinese to traditional Chinese for published site content."""

from __future__ import annotations

import re

WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
PROTECTED_RE = re.compile(
    r"\[\[[^\]]+\]\]|\[[^\]]+\]\([^)]+\)|https?://[^\s)>\]]+"
)


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
