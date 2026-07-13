"""Shared constants, paths, validation, markdown, CLI, output, and link helpers."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# --- constants ---

AI_SYNTHESIS_PREFIX = "[AI Synthesis]"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TRUNCATED_URL_RE = re.compile(r"\.\.\.")
WIKI_PATH_RE = re.compile(r"`([^`]+\.md)`")
RESOURCE_DIR_RE = re.compile(r"_resources/([^/\]\s]+)")

# --- paths ---


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def resolve_path(base: Path, value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def relative_prefix(root: Path, directory: Path) -> str:
    return str(directory.relative_to(root)).replace("\\", "/")


# --- agents ---


def agents_contract_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "AGENTS.md"


def load_agents_contract(root: Path | None = None) -> str:
    return agents_contract_path(root).read_text(encoding="utf-8")


# --- validate ---


def require_mapping(payload: dict[str, Any], key: str, *, label: str = "") -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        field = label or key
        raise ValueError(f"{field} must be an object.")
    return value


def validate_slug(slug: str, label: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"{label} slug is invalid: {slug}")


def validate_synthesis_labels(items: list[str], label: str) -> None:
    for item in items:
        text = item.strip()
        if not text:
            raise ValueError(f"{label} contains an empty bullet.")
        if "AI Synthesis" in text and not text.startswith(AI_SYNTHESIS_PREFIX):
            raise ValueError(f"{label} inference must start with '{AI_SYNTHESIS_PREFIX}'.")


_FILENAME_PUNCTUATION_MAP = str.maketrans(
    {
        "\uff1f": "?",  # fullwidth question mark
        "\uff01": "!",  # fullwidth exclamation
        "\uff0c": ",",  # fullwidth comma
        "\uff1a": ":",  # fullwidth colon
        "\uff1b": ";",  # fullwidth semicolon
        "\uff08": "(",  # fullwidth left paren
        "\uff09": ")",  # fullwidth right paren
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
)


def normalize_path_punctuation(path: str) -> str:
    """Collapse common CJK/ASCII punctuation lookalikes for path comparison."""
    return path.translate(_FILENAME_PUNCTUATION_MAP)


# --- markdown ---


def parse_raw_front_matter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML-like front matter from raw markdown body."""

    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not match:
        return {}, content

    front_matter: dict[str, Any] = {}
    list_key: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - "):
            item = line[4:].strip().strip('"')
            if list_key and isinstance(front_matter.get(list_key), list):
                front_matter[list_key].append(item)
            else:
                authors = front_matter.get("author")
                if isinstance(authors, list):
                    authors.append(item)
                else:
                    front_matter["author"] = [item]
            continue
        key_match = re.match(r"^(\w+):\s*(.*)$", line)
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip().strip('"')
        if key in {"author", "topics", "review_labels", "review_notes"} and not value:
            front_matter[key] = []
            list_key = key
        else:
            front_matter[key] = value
            list_key = None

    body = content[match.end() :]
    return front_matter, body


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def markdown_external_link(label: str, url: str) -> str:
    safe_label = label.replace("[", "\\[").replace("]", "\\]")
    return f"[{safe_label}]({url})"


# --- cli ---

LLM_PROVIDER_CHOICES = ("mlx", "gemini", "openai", "fixture")


def add_llm_provider_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        default=None,
        choices=LLM_PROVIDER_CHOICES,
        help="LLM provider backend (default: LLM_PROVIDER from .env, usually mlx).",
    )


def add_dry_run_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render without writing files.",
    )


def add_wiki_paths_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wiki", default="newswiki/wiki", help="Wiki directory.")
    parser.add_argument("--outputs", default="newswiki/outputs", help="Directory for saved outputs.")
    parser.add_argument("--source", default="newswiki/raw", help="Raw source directory.")


def reject_fixture_provider(name: str | None, *, script: str) -> bool:
    """Print guidance and return True when fixture provider cannot run standalone."""

    if name == "fixture":
        print(f"[{script}] fixture provider requires injecting responses in tests or API calls.")
        return True
    return False


# --- output ---


def sanitize_slug(value: str, *, fallback: str) -> str:
    if value and SLUG_RE.fullmatch(value):
        return value
    safe = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    safe = re.sub(r"-+", "-", safe)
    return safe[:60] or fallback


def slug_from_url_path(url: str) -> str:
    segment = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return sanitize_slug(segment, fallback="")


def derive_article_slug_fallback(article: dict[str, Any], raw_stem: str) -> str:
    front_matter = article.get("front_matter")
    if isinstance(front_matter, dict):
        source = str(front_matter.get("source", "")).strip()
        if source:
            url_slug = slug_from_url_path(source)
            if url_slug and len(url_slug) >= 4:
                return url_slug

    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", raw_stem)
    if match:
        date_part, rest = match.groups()
        rest_slug = sanitize_slug(rest, fallback="")
        if rest_slug:
            return f"{date_part}-{rest_slug}"[:60]
        return f"{date_part}-article"

    return sanitize_slug(raw_stem, fallback="article")


def resolve_output_slug(question: str, filename_slug: str, *, fallback: str) -> str:
    if filename_slug and SLUG_RE.fullmatch(filename_slug):
        return filename_slug
    return sanitize_slug(question, fallback=fallback)


def assert_valid_slug(slug: str, *, field: str) -> None:
    if slug and not SLUG_RE.fullmatch(slug):
        raise ValueError(f"{field} is invalid: {slug}")


def save_dated_markdown(
    outputs_dir: Path,
    *,
    slug: str,
    body: str,
    dry_run: bool = False,
) -> Path | None:
    target = outputs_dir / f"{slug}-{date.today().isoformat()}.md"
    if dry_run:
        return target

    outputs_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def render_citation_line(citation: dict[str, Any]) -> str:
    ctype = citation.get("type")
    note = str(citation.get("note", "")).strip()
    if ctype == "external":
        url = str(citation.get("url", "")).strip()
        return f"- **external**: [{url}]({url}) — {note}"
    link = str(citation.get("link", "")).strip()
    path = str(citation.get("path", "")).strip()
    return f"- **{ctype}**: {link} (`{path}`) — {note}"


def output_filename(
    response: dict[str, Any],
    *,
    outputs_prefix: str,
    slug_fallback: str,
    question: str = "",
) -> str:
    output = require_mapping(response, "output")
    if not output.get("should_save"):
        return ""
    slug = sanitize_slug(
        str(output.get("filename_slug", "")).strip(),
        fallback=slug_fallback if not question else sanitize_slug(question, fallback=slug_fallback),
    )
    return f"{outputs_prefix}/{slug}-{date.today().isoformat()}.md"


def render_output_front_matter(
    *,
    title: str,
    tags: list[str],
    extra_fields: dict[str, str] | None = None,
) -> list[str]:
    today = date.today().isoformat()
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"created: {today}",
    ]
    for key, value in (extra_fields or {}).items():
        lines.append(f"{key}: {yaml_quote(value)}")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    return lines


# --- links ---


@dataclass
class WikiLinkResolver:
    """Resolve [[wiki links]] against configured wiki and source trees."""

    root: Path
    wiki_dir: Path
    source_dir: Path
    wiki_prefix: str
    source_prefix: str

    def extract_links(self, content: str) -> list[str]:
        return [match.group(1).strip() for match in WIKI_LINK_RE.finditer(content)]

    def resolve(self, target: str, source_file: Path) -> tuple[bool, str]:
        if target.startswith("http://") or target.startswith("https://"):
            return True, "external URL"

        if target.startswith("../") or target.startswith(self.source_prefix) or "raw/" in target:
            raw = self._resolve_raw_link(target)
            if raw:
                return True, str(raw.relative_to(self.root)).replace("\\", "/")
            return False, "raw target not found"

        for candidate in self._wiki_candidates(target, source_file):
            if candidate.exists():
                return True, str(candidate.relative_to(self.root)).replace("\\", "/")

        return False, "wiki target not found"

    def _wiki_candidates(self, target: str, source_file: Path) -> list[Path]:
        candidates: list[Path] = []
        if target.startswith("../") or target.startswith("newswiki/raw"):
            return candidates

        if "/" in target:
            base = self.wiki_dir / target
            if target.endswith("_index"):
                candidates.append(base.with_suffix(".md"))
            candidates.append(base.with_suffix(".md") if not target.endswith(".md") else base)
            if not target.endswith(".md"):
                candidates.append(self.wiki_dir / f"{target}.md")
        else:
            topic_dir = source_file.parent if source_file.parent != self.wiki_dir else None
            if topic_dir:
                candidates.append(topic_dir / f"{target}.md")
            candidates.append(self.wiki_dir / f"{target}.md")
            candidates.append(self.wiki_dir / target / "_index.md")

        seen: set[Path] = set()
        unique: list[Path] = []
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(candidate)
        return unique

    def _resolve_raw_link(self, target: str) -> Path | None:
        if target.startswith("../"):
            resolved = (self.wiki_dir / target).resolve()
            if resolved.exists():
                return resolved
        raw_path = self.source_dir / target.replace(f"{self.source_prefix}/", "", 1)
        if raw_path.exists():
            return raw_path
        archive_path = self.source_dir / "archive" / Path(target).name
        if archive_path.exists():
            return archive_path
        return None
