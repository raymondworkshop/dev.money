"""Human review labels and queue for raw inbox files."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from wiki.common import parse_raw_front_matter, yaml_quote

SYNC_STATUS_KEY = "sync_status"
REVIEW_LABELS_KEY = "review_labels"
REVIEW_NOTES_KEY = "review_notes"
PROPOSED_TOPIC_KEY = "proposed_topic"
REVIEW_QUEUE_NAME = "REVIEW.md"

LABEL_TOPIC_NOT_CANONICAL = "topic-not-canonical"
LABEL_LLM_NEEDS_REVIEW = "llm-needs-review"

LIST_FRONT_MATTER_KEYS = frozenset({"author", "topics", REVIEW_LABELS_KEY, REVIEW_NOTES_KEY})


def is_review_queue_file(path: Path) -> bool:
    return path.name == REVIEW_QUEUE_NAME


def is_raw_marked_for_review(path: Path) -> bool:
    if is_review_queue_file(path):
        return False
    front_matter, _ = parse_raw_front_matter(path.read_text(encoding="utf-8"))
    return str(front_matter.get(SYNC_STATUS_KEY, "")).strip() == "needs_review"


def infer_review_labels(review_notes: list[str]) -> list[str]:
    if any("not canonical" in note.lower() for note in review_notes):
        return [LABEL_TOPIC_NOT_CANONICAL]
    return [LABEL_LLM_NEEDS_REVIEW]


def _render_front_matter(front_matter: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in front_matter.items():
        if key in LIST_FRONT_MATTER_KEYS and isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                text = str(item).strip()
                if text.startswith('"') or text.startswith("[[") or text.startswith("#"):
                    lines.append(f"  - {text}")
                else:
                    lines.append(f"  - {yaml_quote(text)}")
            continue
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            text = str(value).strip()
            if key in {"title", "source", "description", PROPOSED_TOPIC_KEY, SYNC_STATUS_KEY} or " " in text:
                lines.append(f"{key}: {yaml_quote(text)}")
            else:
                lines.append(f"{key}: {text}")
    lines.append("---")
    return "\n".join(lines)


def mark_raw_needs_review(
    raw_path: Path,
    *,
    labels: list[str],
    notes: list[str],
    proposed_topic: str = "",
) -> None:
    content = raw_path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(content)

    front_matter[SYNC_STATUS_KEY] = "needs_review"
    existing_labels = front_matter.get(REVIEW_LABELS_KEY, [])
    if isinstance(existing_labels, str):
        existing_labels = [existing_labels]
    front_matter[REVIEW_LABELS_KEY] = sorted({*(existing_labels or []), *labels})

    merged_notes: list[str] = []
    existing_notes = front_matter.get(REVIEW_NOTES_KEY, []) or []
    for note in [*existing_notes, *notes]:
        text = str(note).strip()
        if text and text not in merged_notes:
            merged_notes.append(text)
    front_matter[REVIEW_NOTES_KEY] = merged_notes

    if proposed_topic:
        front_matter[PROPOSED_TOPIC_KEY] = proposed_topic

    raw_path.write_text(f"{_render_front_matter(front_matter)}\n\n{body.lstrip()}", encoding="utf-8")


def clear_raw_review_markers(raw_path: Path) -> None:
    content = raw_path.read_text(encoding="utf-8")
    front_matter, body = parse_raw_front_matter(content)
    for key in (SYNC_STATUS_KEY, REVIEW_LABELS_KEY, REVIEW_NOTES_KEY, PROPOSED_TOPIC_KEY):
        front_matter.pop(key, None)
    if front_matter:
        raw_path.write_text(f"{_render_front_matter(front_matter)}\n\n{body.lstrip()}", encoding="utf-8")
    else:
        raw_path.write_text(body.lstrip(), encoding="utf-8")


def _queue_row(raw_path: Path) -> str | None:
    if not is_raw_marked_for_review(raw_path):
        return None

    front_matter, _ = parse_raw_front_matter(raw_path.read_text(encoding="utf-8"))
    labels = front_matter.get(REVIEW_LABELS_KEY, [])
    if isinstance(labels, str):
        labels = [labels]
    notes = front_matter.get(REVIEW_NOTES_KEY, [])
    if isinstance(notes, str):
        notes = [notes]
    proposed = str(front_matter.get(PROPOSED_TOPIC_KEY, "")).strip()
    label_text = ", ".join(f"`{label}`" for label in labels) if labels else "—"
    note_text = " ".join(str(note) for note in notes).replace("|", "\\|")
    proposed_text = f"`{proposed}`" if proposed else "—"
    return f"| {raw_path.name} | {label_text} | {proposed_text} | {note_text} |"


def rebuild_review_queue(raw_dir: Path) -> Path | None:
    rows: list[str] = []
    for path in sorted(raw_dir.glob("*.md")):
        if is_review_queue_file(path):
            continue
        row = _queue_row(path)
        if row:
            rows.append(row)

    queue_path = raw_dir / REVIEW_QUEUE_NAME
    if not rows:
        if queue_path.exists():
            queue_path.unlink()
        return None

    content = "\n".join(
        [
            "# Sync Review Queue",
            "",
            f"**Last Updated:** {date.today().isoformat()}",
            "",
            "Raw inbox files labeled `sync_status: needs_review`. Clear labels after fixing, then rerun sync.",
            "",
            "| File | Review Labels | Proposed Topic | Notes |",
            "|------|---------------|----------------|-------|",
            *rows,
            "",
        ]
    )
    queue_path.write_text(content, encoding="utf-8")
    return queue_path
