"""Deterministic wiki audit harness for dev.money."""

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

WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
SEVERITIES = {"critical", "warning", "info"}
CATEGORIES = {"broken_link", "missing_reference", "coverage_gap", "quality", "other"}
EVIDENCE_TYPES = {"wiki", "raw", "external"}
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
    """Configure wiki, outputs, and source directories for the audit harness."""

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
class BrokenLink:
    source_path: str
    link: str
    target: str
    reason: str


@dataclass
class IndexGap:
    index_path: str
    link: str
    target: str
    reason: str


@dataclass
class DeterministicFindings:
    broken_links: list[BrokenLink] = field(default_factory=list)
    index_gaps: list[IndexGap] = field(default_factory=list)
    files_scanned: int = 0


@dataclass
class AuditResult:
    dry_run: bool = False
    output_path: str | None = None
    saved: bool = False
    deterministic: DeterministicFindings = field(default_factory=DeterministicFindings)
    review_notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def iter_wiki_markdown_files() -> list[Path]:
    if not WIKI_DIR.exists():
        return []
    return sorted(path for path in WIKI_DIR.rglob("*.md") if path.is_file())


def build_file_inventory() -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    for path in iter_wiki_markdown_files():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        inventory.append({"path": rel, "name": path.name})
    return inventory


def extract_wiki_links(content: str) -> list[str]:
    return [match.group(1).strip() for match in WIKI_LINK_RE.finditer(content)]


def _wiki_candidates(target: str, source_file: Path) -> list[Path]:
    candidates: list[Path] = []
    if target.startswith("../") or target.startswith("newswiki/raw"):
        return candidates

    if "/" in target:
        base = WIKI_DIR / target
        if target.endswith("_index"):
            candidates.append(base.with_suffix(".md"))
        candidates.append(base.with_suffix(".md") if not target.endswith(".md") else base)
        if not target.endswith(".md"):
            candidates.append(WIKI_DIR / f"{target}.md")
    else:
        topic_dir = source_file.parent if source_file.parent != WIKI_DIR else None
        if topic_dir:
            candidates.append(topic_dir / f"{target}.md")
        candidates.append(WIKI_DIR / f"{target}.md")
        candidates.append(WIKI_DIR / target / "_index.md")

    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(candidate)
    return unique


def _resolve_raw_link(target: str) -> Path | None:
    if target.startswith("../"):
        resolved = (WIKI_DIR / target).resolve()
        if resolved.exists():
            return resolved
    raw_path = SOURCE_DIR / target.replace(f"{SOURCE_PREFIX}/", "", 1)
    if raw_path.exists():
        return raw_path
    archive_path = SOURCE_DIR / "archive" / Path(target).name
    if archive_path.exists():
        return archive_path
    return None


def resolve_wiki_link(target: str, source_file: Path) -> tuple[bool, str]:
    if target.startswith("http://") or target.startswith("https://"):
        return True, "external URL"

    if target.startswith("../") or target.startswith(SOURCE_PREFIX) or "raw/" in target:
        raw = _resolve_raw_link(target)
        if raw:
            return True, str(raw.relative_to(ROOT)).replace("\\", "/")
        return False, "raw target not found"

    for candidate in _wiki_candidates(target, source_file):
        if candidate.exists():
            return True, str(candidate.relative_to(ROOT)).replace("\\", "/")

    return False, "wiki target not found"


def scan_broken_links() -> list[BrokenLink]:
    broken: list[BrokenLink] = []
    for path in iter_wiki_markdown_files():
        content = path.read_text(encoding="utf-8")
        source_rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for target in extract_wiki_links(content):
            ok, reason = resolve_wiki_link(target, path)
            if not ok:
                broken.append(
                    BrokenLink(
                        source_path=source_rel,
                        link=f"[[{target}]]",
                        target=target,
                        reason=reason,
                    )
                )
    return broken


def scan_index_gaps() -> list[IndexGap]:
    gaps: list[IndexGap] = []
    index_files = [ROOT_INDEX] if ROOT_INDEX.exists() else []
    index_files.extend(sorted(WIKI_DIR.glob("*/_index.md")))

    for index_path in index_files:
        content = index_path.read_text(encoding="utf-8")
        index_rel = str(index_path.relative_to(ROOT)).replace("\\", "/")
        for target in extract_wiki_links(content):
            ok, reason = resolve_wiki_link(target, index_path)
            if not ok:
                gaps.append(
                    IndexGap(
                        index_path=index_rel,
                        link=f"[[{target}]]",
                        target=target,
                        reason=reason,
                    )
                )
    return gaps


def run_deterministic_checks() -> DeterministicFindings:
    files = iter_wiki_markdown_files()
    return DeterministicFindings(
        broken_links=scan_broken_links(),
        index_gaps=scan_index_gaps(),
        files_scanned=len(files),
    )


def _format_deterministic_context(findings: DeterministicFindings) -> str:
    parts = [
        f"Files scanned: {findings.files_scanned}",
        f"Broken links (harness): {len(findings.broken_links)}",
        f"Index gaps (harness): {len(findings.index_gaps)}",
    ]

    if findings.broken_links:
        parts.append("\n### Harness broken links")
        for item in findings.broken_links[:50]:
            parts.append(
                f"- {item.source_path}: {item.link} -> {item.reason} (target={item.target})"
            )

    if findings.index_gaps:
        parts.append("\n### Harness index gaps")
        for item in findings.index_gaps[:50]:
            parts.append(
                f"- {item.index_path}: {item.link} -> {item.reason} (target={item.target})"
            )

    inventory = build_file_inventory()
    if inventory:
        parts.append("\n### Wiki file inventory")
        for entry in inventory[:100]:
            parts.append(f"- {entry['path']}")

    return "\n".join(parts)


def build_audit_prompt(findings: DeterministicFindings | None = None) -> LLMRequest:
    resolved = findings or run_deterministic_checks()
    system = GEMINI_CONF.read_text(encoding="utf-8")
    prompt = f"""Audit the investment wiki following the Audit contract in GEMINI.md.

Configured paths:
- Wiki prefix: {WIKI_PREFIX}/
- Source prefix: {SOURCE_PREFIX}/ (including {SOURCE_PREFIX}/archive/ for archived raw files)
- Outputs prefix: {OUTPUTS_PREFIX}/

Deterministic harness findings (verify, extend, and cite in your report):
{_format_deterministic_context(resolved)}

Return strict JSON only. Do not wrap the answer in markdown fences.
"""
    return LLMRequest(system=system, prompt=prompt)


def _require_mapping(response: dict[str, Any], key: str) -> dict[str, Any]:
    value = response.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Audit field '{key}' must be an object.")
    return value


def _validate_evidence(evidence: dict[str, Any], finding_index: int, evidence_index: int) -> None:
    etype = evidence.get("type")
    if etype not in EVIDENCE_TYPES:
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}] type must be one of "
            f"{sorted(EVIDENCE_TYPES)}."
        )

    note = str(evidence.get("note", "")).strip()
    if not note:
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}].note is required."
        )

    if etype == "external":
        url = str(evidence.get("url", "")).strip()
        if not url.startswith("http"):
            raise ValueError(
                f"findings[{finding_index}].evidence[{evidence_index}].url must be an http(s) URL."
            )
        return

    path = str(evidence.get("path", "")).strip()
    link = str(evidence.get("link", "")).strip()
    if not path:
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}].path is required for {etype}."
        )
    if not link.startswith("[[") or "]]" not in link:
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}].link must be a clickable [[wiki link]]."
        )

    if etype == "wiki" and not path.startswith(f"{WIKI_PREFIX}/"):
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}].path must live under {WIKI_PREFIX}/."
        )
    if etype == "raw" and not path.startswith(f"{SOURCE_PREFIX}/"):
        raise ValueError(
            f"findings[{finding_index}].evidence[{evidence_index}].path must live under {SOURCE_PREFIX}/."
        )


def validate_audit_response(response: dict[str, Any]) -> None:
    summary = str(response.get("summary", "")).strip()
    if not summary:
        raise ValueError("summary is required.")

    findings = response.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list.")

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"findings[{index}] must be an object.")

        title = str(finding.get("title", "")).strip()
        severity = str(finding.get("severity", "")).strip()
        category = str(finding.get("category", "")).strip()
        description = str(finding.get("description", "")).strip()

        if not title:
            raise ValueError(f"findings[{index}].title is required.")
        if severity not in SEVERITIES:
            raise ValueError(f"findings[{index}].severity must be one of {sorted(SEVERITIES)}.")
        if category not in CATEGORIES:
            raise ValueError(f"findings[{index}].category must be one of {sorted(CATEGORIES)}.")
        if not description:
            raise ValueError(f"findings[{index}].description is required.")

        evidence = finding.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"findings[{index}].evidence must be a non-empty list.")
        for evidence_index, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise ValueError(f"findings[{index}].evidence[{evidence_index}] must be an object.")
            _validate_evidence(item, index, evidence_index)

    coverage_gaps = response.get("coverage_gaps", [])
    if coverage_gaps is not None:
        if not isinstance(coverage_gaps, list):
            raise ValueError("coverage_gaps must be a list.")
        for index, gap in enumerate(coverage_gaps):
            if not isinstance(gap, dict):
                raise ValueError(f"coverage_gaps[{index}] must be an object.")
            topic = str(gap.get("topic", "")).strip()
            description = str(gap.get("description", "")).strip()
            if not topic or not description:
                raise ValueError(f"coverage_gaps[{index}] requires topic and description.")

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


def _sanitize_slug(slug: str) -> str:
    if slug and SLUG_RE.fullmatch(slug):
        return slug
    return "wiki-audit"


def render_audit_markdown(response: dict[str, Any], *, deterministic: DeterministicFindings | None = None) -> str:
    today = date.today().isoformat()
    summary = str(response.get("summary", "")).strip()

    parts = [
        "---",
        'title: "Wiki Audit Report"',
        f"created: {today}",
        "tags: [audit-wiki]",
        "---",
        "",
        "# Wiki Audit Report",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]

    findings = response.get("findings", []) or []
    if findings:
        parts.append("## Findings")
        parts.append("")
        for finding in findings:
            severity = finding.get("severity", "info")
            category = finding.get("category", "other")
            title = str(finding.get("title", "")).strip()
            parts.append(f"### {title} ({severity} / {category})")
            parts.append("")
            parts.append(str(finding.get("description", "")).strip())
            parts.append("")
            for evidence in finding.get("evidence", []) or []:
                etype = evidence.get("type")
                note = str(evidence.get("note", "")).strip()
                if etype == "external":
                    url = str(evidence.get("url", "")).strip()
                    parts.append(f"- **external**: [{url}]({url}) — {note}")
                else:
                    link = str(evidence.get("link", "")).strip()
                    path = str(evidence.get("path", "")).strip()
                    parts.append(f"- **{etype}**: {link} (`{path}`) — {note}")
            recommendation = str(finding.get("recommendation", "")).strip()
            if recommendation:
                parts.append("")
                parts.append(f"**Recommendation**: {recommendation}")
            parts.append("")

    coverage_gaps = response.get("coverage_gaps", []) or []
    if coverage_gaps:
        parts.extend(["## Coverage Gaps", ""])
        for gap in coverage_gaps:
            topic = str(gap.get("topic", "")).strip()
            description = str(gap.get("description", "")).strip()
            action = str(gap.get("suggested_action", "")).strip()
            line = f"- **{topic}**: {description}"
            if action:
                line += f" — _Suggested action_: {action}"
            parts.append(line)
        parts.append("")

    if deterministic:
        parts.extend(
            [
                "## Harness Checks",
                "",
                f"- Files scanned: {deterministic.files_scanned}",
                f"- Broken links detected: {len(deterministic.broken_links)}",
                f"- Index gaps detected: {len(deterministic.index_gaps)}",
                "",
            ]
        )
        if deterministic.broken_links:
            parts.append("### Broken Links (deterministic)")
            for item in deterministic.broken_links:
                parts.append(
                    f"- {item.source_path}: {item.link} — {item.reason} (`{item.target}`)"
                )
            parts.append("")

    review_notes = response.get("review_notes") or []
    if review_notes:
        parts.extend(["## Review Notes"])
        for note in review_notes:
            parts.append(f"- {str(note).strip()}")

    return "\n".join(parts).strip() + "\n"


def save_audit_output(
    response: dict[str, Any],
    *,
    dry_run: bool = False,
    deterministic: DeterministicFindings | None = None,
) -> Path | None:
    output = _require_mapping(response, "output")
    if not output.get("should_save"):
        return None

    slug = _sanitize_slug(str(output.get("filename_slug", "")).strip())
    target = OUTPUTS_DIR / f"{slug}-{date.today().isoformat()}.md"

    if dry_run:
        return target

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_audit_markdown(response, deterministic=deterministic),
        encoding="utf-8",
    )
    return target


def run_audit(
    provider: LLMProvider | None = None,
    *,
    dry_run: bool = False,
    response: dict[str, Any] | None = None,
    deterministic: DeterministicFindings | None = None,
) -> AuditResult:
    result = AuditResult(dry_run=dry_run)
    try:
        resolved_deterministic = deterministic or run_deterministic_checks()
        result.deterministic = resolved_deterministic

        if response is not None:
            resolved = response
        elif provider is not None:
            resolved = proposal_from_provider(provider, build_audit_prompt(resolved_deterministic))
        else:
            raise ValueError("run_audit requires provider or injected response.")

        validate_audit_response(resolved)
        result.review_notes = [str(n) for n in resolved.get("review_notes", []) or []]

        markdown = render_audit_markdown(resolved, deterministic=resolved_deterministic)
        if not dry_run and resolved.get("output", {}).get("should_save"):
            saved_path = save_audit_output(
                resolved,
                dry_run=False,
                deterministic=resolved_deterministic,
            )
            if saved_path:
                result.saved = True
                result.output_path = str(saved_path.relative_to(ROOT))
        elif dry_run:
            planned = save_audit_output(
                resolved,
                dry_run=True,
                deterministic=resolved_deterministic,
            )
            if planned:
                result.output_path = str(planned.relative_to(ROOT))

        if not result.output_path and resolved.get("output", {}).get("should_save"):
            slug = _sanitize_slug(str(resolved.get("output", {}).get("filename_slug", "")).strip())
            result.output_path = f"{OUTPUTS_PREFIX}/{slug}-{date.today().isoformat()}.md"

        if dry_run and not result.errors:
            result.review_notes.append(f"Rendered {len(markdown)} bytes (dry run).")
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def _format_result(result: AuditResult) -> str:
    parts = [
        f"files_scanned={result.deterministic.files_scanned}",
        f"broken_links={len(result.deterministic.broken_links)}",
        f"index_gaps={len(result.deterministic.index_gaps)}",
    ]
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
    parser = argparse.ArgumentParser(description="Audit the investment wiki for link and coverage issues.")
    parser.add_argument("--wiki", default=DEFAULT_WIKI, help="Wiki directory.")
    parser.add_argument("--outputs", default=DEFAULT_OUTPUTS, help="Directory for saved audit reports.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Raw source directory for evidence links.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and render without saving output.")
    parser.add_argument("--provider", default="openai", choices=["openai", "fixture"], help="LLM provider backend.")
    args = parser.parse_args()

    configure_paths(wiki=args.wiki, outputs=args.outputs, source=args.source)

    if args.provider == "fixture":
        print("[audit_wiki] fixture provider requires injecting responses in tests or API calls.")
        return 1

    provider = build_provider(args.provider)
    result = run_audit(provider, dry_run=args.dry_run)
    print(f"[audit_wiki] {_format_result(result)}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
