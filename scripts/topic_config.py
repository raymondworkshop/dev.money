"""Editorial topic slugs and optional multi-topic article assignments."""

from __future__ import annotations

from typing import Any

CANONICAL_TOPICS: tuple[str, ...] = (
    "business",
    "tech",
    "design",
    "finance",
    "career",
    "lifestyle",
)

TOPIC_LABELS: dict[str, str] = {
    "business": "Business",
    "tech": "Tech",
    "design": "Design",
    "finance": "Finance",
    "career": "Career",
    "lifestyle": "Lifestyle Trends",
}

# Short blurbs for the grouped root INDEX Topics section.
TOPIC_BLURBS: dict[str, str] = {
    "tech": "AI 算力、模型、机器人与教育科技。",
    "design": "产品设计、自托管体验与科学传播。",
    "finance": "投资、加密资产、房地产与财富管理。",
    "business": "公司战略、创业风投、产业政策与商业航天。",
    "career": "AI 对就业的冲击、职业发展与人事实践。",
    "lifestyle": "健康、育儿、文化趋势与生活方式。",
}

# Grouped homepage Topics nav (### headings + topic lines).
TOPIC_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Tech & Infrastructure", ("tech", "design")),
    ("Finance & Crypto", ("finance",)),
    ("Innovation & Defense", ("business",)),
    ("Labor & Society", ("career", "lifestyle")),
)

# Legacy or LLM-invented slugs remapped to a canonical topic during sync.
TOPIC_ALIASES: dict[str, str] = {
    "ai-infrastructure": "tech",
    "ai-education": "tech",
    "ai-tech": "tech",
    "ai-multimodal-ai": "tech",
    "education-tech": "tech",
    "ai-llm-fine-tuning": "tech",
    "AI_in_education": "tech",
    "nvda": "tech",
    "tech-independence": "design",
    "crypto-finance": "finance",
    "ai-finance": "finance",
    "real-estate": "finance",
    "space-tech": "finance",
    "personal-finance": "lifestyle",
    "work-careers": "career",
    "ai-employment": "career",
    "talent-careers": "career",
    "defense-tech": "business",
    "defense-space": "business",
    "geopolitics-china-policy": "business",
    "health-longevity": "lifestyle",
    "parenting-philosophy": "lifestyle",
    "society": "lifestyle",
    "lifestyle-trends": "lifestyle",
    "Lifestyle Trends": "lifestyle",
}


def is_canonical_topic(slug: str) -> bool:
    return slug.strip() in CANONICAL_TOPICS


def normalize_topic_slug(slug: str) -> str:
    cleaned = slug.strip()
    if is_canonical_topic(cleaned):
        return cleaned
    return TOPIC_ALIASES.get(cleaned, cleaned)


def render_canonical_topics_for_prompt() -> str:
    lines: list[str] = []
    for slug in CANONICAL_TOPICS:
        label = TOPIC_LABELS[slug]
        blurb = TOPIC_BLURBS[slug]
        lines.append(f"- {slug} ({label}): {blurb}")
    return "\n".join(lines)


def topic_hint_from_front_matter(front_matter: dict[str, Any]) -> str:
    topics = front_matter.get("topics")
    if isinstance(topics, list) and topics:
        hints = [normalize_topic_slug(str(item)) for item in topics if str(item).strip()]
        if hints:
            return (
                "Operator hint (prefer when appropriate): "
                f"topic candidates {', '.join(hints)}"
            )
    if isinstance(topics, str) and topics.strip():
        return (
            "Operator hint (prefer when appropriate): "
            f"topic candidate {normalize_topic_slug(topics.strip())}"
        )
    return ""


def _replace_topic_slug_in_path(path: str, old_slug: str, new_slug: str) -> str:
    return path.replace(f"/{old_slug}/", f"/{new_slug}/").replace(f"/{old_slug}", f"/{new_slug}")


def _replace_topic_slug_in_wiki_link(text: str, old_slug: str, new_slug: str) -> str:
    return text.replace(f"[[{old_slug}/", f"[[{new_slug}/")


def remap_proposal_topic_slugs(proposal: dict[str, Any]) -> list[str]:
    """Remap topic slugs in a create_article proposal. Returns harness notes."""

    notes: list[str] = []
    if proposal.get("action") != "create_article":
        return notes

    topic = proposal["topic"]
    article = proposal["article"]
    original_primary = str(topic.get("slug", "")).strip()
    primary = normalize_topic_slug(original_primary)

    if primary != original_primary:
        notes.append(f"Remapped primary topic '{original_primary}' -> '{primary}'.")
        for obj, key in ((topic, "path"), (article, "path")):
            if obj.get(key):
                obj[key] = _replace_topic_slug_in_path(str(obj[key]), original_primary, primary)

        index_updates = proposal.get("index_updates")
        if isinstance(index_updates, dict) and index_updates.get("root_recent_entry"):
            index_updates["root_recent_entry"] = _replace_topic_slug_in_wiki_link(
                str(index_updates["root_recent_entry"]),
                original_primary,
                primary,
            )

        footer = article.get("topic_footer")
        if isinstance(footer, dict):
            topic_links = footer.get("topic_links")
            if isinstance(topic_links, list):
                footer["topic_links"] = [
                    _replace_topic_slug_in_wiki_link(str(link), original_primary, primary)
                    for link in topic_links
                ]
            tags = footer.get("tags")
            if isinstance(tags, list):
                footer["tags"] = [
                    f"#{primary}" if str(tag).strip() == f"#{original_primary}" else str(tag)
                    for tag in tags
                ]

    topic["slug"] = primary
    topic["is_new"] = False

    raw_topics = article.get("topics")
    if isinstance(raw_topics, list):
        normalized: list[str] = []
        for item in raw_topics:
            mapped = normalize_topic_slug(str(item).strip())
            if mapped and mapped not in normalized:
                normalized.append(mapped)
        if primary not in normalized:
            normalized.insert(0, primary)
        else:
            normalized = [primary, *[slug for slug in normalized if slug != primary]]

        kept: list[str] = []
        for slug in normalized:
            if is_canonical_topic(slug):
                kept.append(slug)
            else:
                notes.append(f"Dropped non-canonical secondary topic '{slug}'.")
        article["topics"] = kept or [primary]

    return notes


def enforce_canonical_topics(proposal: dict[str, Any]) -> dict[str, Any]:
    """Remap aliases and downgrade unknown primaries to needs_review."""

    if proposal.get("action") != "create_article":
        return proposal

    notes = remap_proposal_topic_slugs(proposal)
    primary = str(proposal["topic"]["slug"])

    if is_canonical_topic(primary):
        review_notes = [str(item) for item in proposal.get("review_notes") or []]
        review_notes.extend(notes)
        proposal["review_notes"] = review_notes
        return proposal

    canonical_list = ", ".join(CANONICAL_TOPICS)
    review_notes = [str(item) for item in proposal.get("review_notes") or []]
    review_notes.extend(notes)
    review_notes.append(f"Topic '{primary}' is not canonical. Pick one of: {canonical_list}.")
    return {
        "action": "needs_review",
        "source_file": proposal["source_file"],
        "review_notes": review_notes,
        "proposed_topic": primary,
    }


def render_root_topics_section() -> str:
    """Render the grouped ## Topics block for INDEX.md."""

    lines = ["## Topics", ""]
    for group_name, slugs in TOPIC_GROUPS:
        lines.append(f"### {group_name}")
        for slug in slugs:
            label = TOPIC_LABELS[slug]
            blurb = TOPIC_BLURBS[slug]
            lines.append(f"- [[{slug}/_index|{label}]]: {blurb}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

# Optional secondary topics keyed by article filename. Primary topic is the file folder.
ARTICLE_EXTRA_TOPICS: dict[str, list[str]] = {
    "2026-02-23-ai-valuation-back-to-back-financing.md": ["finance"],
    "2026-03-11-aaru-ai-simulates-human-behavior.md": ["tech"],
    "2026-05-21-nvda-undervalued.md": ["tech"],
    "2026-05-27-spacex-investment.md": ["business"],
    "2026-05-28-cheap-humanoid-robots.md": ["career"],
    "2026-05-29-ai-fact-checking.md": ["career"],
    "67-age-entrepreneurship.md": ["career"],
    "ai-digital-doubles-workforce-20260602.md": ["career"],
    "berkshire-japan-us-housing-opportunity.md": ["finance"],
    "doerr-ai-tsunami.md": ["tech"],
    "estonia-ai-education-experiment.md": ["lifestyle"],
    "leopold-aschenbrenner-situational-awareness.md": ["tech", "business"],
    "nvidia-ai-agent-pcs-launch.md": ["tech"],
    "science-communication-actor-method.md": ["lifestyle"],
    "spacex-ipo-wealth-management.md": ["business"],
    "2026-05-11-divorce-financial-infidelity.md": ["finance"],
    "us-elderly-generosity-support.md": ["finance"],
}


def topic_link(slug: str) -> str:
    label = TOPIC_LABELS.get(slug, slug.replace("-", " ").title())
    return f"[[{slug}/_index|{label}]]"


def article_topics_for_path(article_path_name: str, primary_topic: str) -> list[str]:
    """Return deduped topic slugs with primary topic first."""

    topics = [primary_topic]
    for slug in ARTICLE_EXTRA_TOPICS.get(article_path_name, []):
        if slug not in topics:
            topics.append(slug)
    return topics
