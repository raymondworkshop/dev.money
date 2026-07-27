"""Integrated unit + pipeline tests for dev.news-wiki scripts."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from analyze_lib import (
    build_markdown,
    evaluate,
    fetch_financial_report,
    free_cash_flow,
    operating_margin,
    parse_report,
    peg_ratio,
    read_raw_report,
    revenue_growth,
    write_report,
)
import wiki.sync as sync_module
from wiki.review import mark_raw_needs_review
from wiki.sync import (
    CompileResult,
    apply_proposal,
    append_status_row,
    archive_source,
    build_compile_prompt,
    build_status_row,
    configure_paths,
    normalize_proposal_language,
    normalize_proposal_paths,
    normalize_proposal_slugs,
    normalize_proposal_source_file,
    normalize_wiki_path,
    parse_raw_front_matter,
    remove_raw_source,
    render_article_markdown,
    run_sync,
    scan_pending_files,
    strip_raw_body_for_prompt,
    summarize_sync_results,
    sync_file,
    update_indexes,
    validate_proposal,
)
from wiki.common import article_language, slug_fallback_from_raw, takeaways_heading
from llm_provider import (
    JSON_RETRY_PROMPT,
    FallbackProvider,
    FixtureProvider,
    GeminiProvider,
    LLMRequest,
    OpenAICompatibleProvider,
    build_provider,
    default_provider,
    extract_json_object,
    fallback_provider_chain,
    proposal_from_provider,
    resolve_max_tokens,
    resolve_model,
    resolve_temperature,
)
import wiki.site as prepare_module
from wiki.site import (
    convert_markdown,
    convert_visible_text,
    prepare_content,
    trim_recent_articles_for_site,
    trim_related_articles_for_site,
    trim_topics_groups_for_site,
)
import wiki.query as query_module
from wiki.query import (
    build_query_prompt,
    build_wiki_context,
    configure_paths,
    render_query_markdown,
    run_query,
    save_query_output,
    validate_query_response,
)
import wiki.audit as audit_module
from wiki.audit import (
    build_audit_prompt,
    configure_paths,
    extract_wiki_links,
    render_audit_markdown,
    resolve_wiki_link,
    run_audit,
    run_deterministic_checks,
    save_audit_output,
    scan_broken_links,
    validate_audit_response,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "compile"
QUERY_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "query"
AUDIT_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "audit"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def load_text_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def load_query_fixture(name: str) -> dict:
    return json.loads((QUERY_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def load_audit_fixture(name: str) -> dict:
    return json.loads((AUDIT_FIXTURES_DIR / name).read_text(encoding="utf-8"))


@contextmanager
def sync_workspace(
    *,
    source: str = "newswiki/raw",
    wiki: str = "newswiki/wiki",
    archive: str | None = None,
):
    """Patch wiki.sync paths to an isolated temp workspace."""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original = {
            "ROOT": sync_module.ROOT,
            "RAW_DIR": sync_module.RAW_DIR,
            "ARCHIVE_DIR": sync_module.ARCHIVE_DIR,
            "WIKI_DIR": sync_module.WIKI_DIR,
            "RESOURCES_DIR": sync_module.RESOURCES_DIR,
            "ROOT_INDEX": sync_module.ROOT_INDEX,
            "CACHE_PATH": sync_module.CACHE_PATH,
            "STATUS_PATH": sync_module.STATUS_PATH,
            "SOURCE_PREFIX": sync_module.SOURCE_PREFIX,
            "WIKI_PREFIX": sync_module.WIKI_PREFIX,
        }

        sync_module.ROOT = tmp_path
        sync_module.configure_paths(
            root=tmp_path,
            source=source,
            wiki=wiki,
            archive=archive or f"{source}/archive",
        )

        sync_module.RAW_DIR.mkdir(parents=True, exist_ok=True)
        sync_module.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        sync_module.WIKI_DIR.mkdir(parents=True, exist_ok=True)
        sync_module.RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
        sync_module.ROOT_INDEX.write_text("## Recent Articles\n", encoding="utf-8")

        try:
            yield tmp_path
        finally:
            for key, value in original.items():
                setattr(sync_module, key, value)


@contextmanager
def query_workspace(
    *,
    wiki: str = "newswiki/wiki",
    outputs: str = "newswiki/outputs",
    source: str = "newswiki/raw",
):
    """Patch wiki.query paths to an isolated temp workspace."""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original = {
            "ROOT": query_module.ROOT,
            "WIKI_DIR": query_module.WIKI_DIR,
            "OUTPUTS_DIR": query_module.OUTPUTS_DIR,
            "SOURCE_DIR": query_module.SOURCE_DIR,
            "ROOT_INDEX": query_module.ROOT_INDEX,
            "WIKI_PREFIX": query_module.WIKI_PREFIX,
            "SOURCE_PREFIX": query_module.SOURCE_PREFIX,
            "OUTPUTS_PREFIX": query_module.OUTPUTS_PREFIX,
        }

        query_module.ROOT = tmp_path
        query_module.configure_paths(
            root=tmp_path,
            wiki=wiki,
            outputs=outputs,
            source=source,
        )

        query_module.WIKI_DIR.mkdir(parents=True, exist_ok=True)
        query_module.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        query_module.SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        query_module.ROOT_INDEX.write_text("## Recent Articles\n", encoding="utf-8")

        try:
            yield tmp_path
        finally:
            for key, value in original.items():
                setattr(query_module, key, value)


@contextmanager
def audit_workspace(
    *,
    wiki: str = "newswiki/wiki",
    outputs: str = "newswiki/outputs",
    source: str = "newswiki/raw",
):
    """Patch wiki.audit paths to an isolated temp workspace."""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original = {
            "ROOT": audit_module.ROOT,
            "WIKI_DIR": audit_module.WIKI_DIR,
            "OUTPUTS_DIR": audit_module.OUTPUTS_DIR,
            "SOURCE_DIR": audit_module.SOURCE_DIR,
            "ROOT_INDEX": audit_module.ROOT_INDEX,
            "WIKI_PREFIX": audit_module.WIKI_PREFIX,
            "SOURCE_PREFIX": audit_module.SOURCE_PREFIX,
            "OUTPUTS_PREFIX": audit_module.OUTPUTS_PREFIX,
        }

        audit_module.ROOT = tmp_path
        audit_module.configure_paths(
            root=tmp_path,
            wiki=wiki,
            outputs=outputs,
            source=source,
        )

        audit_module.WIKI_DIR.mkdir(parents=True, exist_ok=True)
        audit_module.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        audit_module.SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        audit_module.ROOT_INDEX.write_text("## Recent Articles\n", encoding="utf-8")

        try:
            yield tmp_path
        finally:
            for key, value in original.items():
                setattr(audit_module, key, value)


class MetricsTests(unittest.TestCase):
    def test_operating_margin(self) -> None:
        self.assertAlmostEqual(operating_margin(25, 100), 0.25)

    def test_revenue_growth(self) -> None:
        self.assertAlmostEqual(revenue_growth(120, 100), 0.2)

    def test_free_cash_flow(self) -> None:
        self.assertEqual(free_cash_flow(42, 10), 32)

    def test_peg_ratio(self) -> None:
        self.assertAlmostEqual(peg_ratio(18, 24), 0.75)


class PipelineTests(unittest.TestCase):
    def test_end_to_end_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_dir = tmp_path / "raw"
            out_dir = tmp_path / "outputs"

            raw_path = fetch_financial_report("AAPL", raw_dir=raw_dir)
            raw = read_raw_report(raw_path)
            parsed = parse_report(raw)
            evaluation = evaluate(parsed)
            md = build_markdown(parsed, evaluation)
            report_path = write_report(parsed, evaluation, output_dir=out_dir)

            self.assertIn("AAPL", md)
            self.assertTrue(0.0 <= evaluation.score <= 1.0)
            self.assertTrue(report_path.exists())


class SyncWikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_proposal = load_fixture("sample_proposal.json")
        cls.sample_raw = load_text_fixture("sample_raw.md")
        cls.chinese_raw = load_text_fixture("chinese_raw.md")

    def _seed_topic_index(self) -> None:
        topic_dir = sync_module.WIKI_DIR / "tech"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "_index.md").write_text(
            "# Tech\n\n## 相关文章\n",
            encoding="utf-8",
        )

    def _raw_file(self, name: str = "2026-05-30-sample.md", content: str | None = None) -> Path:
        raw_file = sync_module.RAW_DIR / name
        raw_file.write_text(content or self.sample_raw, encoding="utf-8")
        return raw_file

    def test_build_compile_prompt_requires_chinese_output_for_chinese_source(self) -> None:
        with sync_workspace():
            raw = (
                "---\ntitle: \"示例中文标题\"\nsource: https://example.com/zh\n"
                "created: 2026-07-13\ndescription: \"这是中文摘要说明文字。\"\n---\n"
                "正文讨论人工智能如何影响药物研发与投资回报。\n"
            )
            path = self._raw_file("2026-07-13-chinese.md", content=raw)
            request = build_compile_prompt(path)
            self.assertIn("Source language: Chinese", request.prompt)
            self.assertIn("Do not translate the article into English", request.prompt)
            self.assertIn("核心观点", request.prompt)

    def test_strip_raw_body_for_prompt_removes_svg_and_html(self) -> None:
        noisy = (
            "Lead paragraph.\n"
            '<svg aria-hidden="true" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>\n'
            "<div>Keep this text</div>\n"
            "Tail paragraph."
        )
        cleaned = strip_raw_body_for_prompt(noisy)
        self.assertNotIn("<svg", cleaned)
        self.assertNotIn("<div>", cleaned)
        self.assertIn("Lead paragraph.", cleaned)
        self.assertIn("Keep this text", cleaned)
        self.assertIn("Tail paragraph.", cleaned)

    def test_build_compile_prompt_strips_svg_from_body(self) -> None:
        with sync_workspace():
            body = (
                "Visible prose about Ello.\n"
                '<svg viewBox="0 0 100 100">' + ("M1 1 " * 500) + "</svg>\n"
            )
            raw = (
                "---\ntitle: Ello\nsource: https://example.com\n"
                "created: 2026-07-10\n---\n" + body
            )
            path = self._raw_file("2026-07-10-ello.md", content=raw)
            request = build_compile_prompt(path)
            self.assertIn("Visible prose about Ello.", request.prompt)
            self.assertNotIn("<svg", request.prompt)
            self.assertNotIn("M1 1 M1 1", request.prompt)

    def test_parse_fixture_raw_front_matter(self) -> None:
        front_matter, body = parse_raw_front_matter(self.sample_raw)
        self.assertEqual(front_matter["title"], "Sample Article")
        self.assertEqual(front_matter["author"], ["[[Author Name]]"])
        self.assertIn("[[Company]]", body)

    def test_parse_chinese_fixture_and_no_front_matter(self) -> None:
        front_matter, body = parse_raw_front_matter(self.chinese_raw)
        self.assertEqual(front_matter["title"], "示例文章")
        self.assertIn("正文内容", body)

        empty_front, plain_body = parse_raw_front_matter("No front matter here.")
        self.assertEqual(empty_front, {})
        self.assertEqual(plain_body, "No front matter here.")

    def test_validate_fixture_proposal(self) -> None:
        raw_path = Path("2026-05-30-sample.md")
        validate_proposal(self.sample_proposal, raw_path)

    def test_validate_rejects_bad_source_file(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["source_file"] = "newswiki/raw/wrong.md"
        with self.assertRaisesRegex(ValueError, "source_file"):
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_normalize_proposal_source_file_repairs_ascii_punctuation(self) -> None:
        raw_name = "2026-07-09-时薪33美元的开市客收银员，如何攒出百万身家？.md"
        raw_path = Path(raw_name)
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["source_file"] = f"newswiki/raw/{raw_name.replace('？', '?')}"
        normalize_proposal_source_file(proposal, raw_path)
        validate_proposal(proposal, raw_path)
        self.assertEqual(proposal["source_file"], f"newswiki/raw/{raw_name}")

    def test_validate_rejects_nested_article_path(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["article"]["path"] = "newswiki/wiki/tech/ai-infrastructure/2026-05-30-sample-article.md"
        with self.assertRaisesRegex(ValueError, "flat under canonical topic"):
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_slug_fallback_from_raw_uses_ascii_fragments(self) -> None:
        slug = slug_fallback_from_raw(Path("2026-07-05-上斜哑铃卧推_Keep.md"))
        self.assertRegex(slug, r"^2026-07-05-keep$")

    def test_slug_fallback_from_raw_hashes_pure_non_ascii(self) -> None:
        raw_path = Path("2026-07-04-贝佐斯如何学会拉拢特朗普并为蓝色起源狂揽合约.md")
        slug = slug_fallback_from_raw(raw_path)
        self.assertRegex(slug, r"^2026-07-04-article-[a-f0-9]{8}$")

    def test_normalize_proposal_slugs_fixes_chinese_article_slug(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        chinese_slug = "贝佐斯如何学会拉拢特朗普并为蓝色起源狂揽合约"
        proposal["article"]["slug"] = chinese_slug
        proposal["article"]["path"] = f"newswiki/wiki/business/{chinese_slug}.md"
        # No usable English URL path — fall back to dated hash slug from the raw filename.
        proposal["article"]["front_matter"]["source"] = "https://example.com/"
        proposal["index_updates"]["topic_index_entry"] = (
            f"- [[{chinese_slug}|贝佐斯如何学会拉拢特朗普并为蓝色起源狂揽合约]] (2026-07-04) - Summary"
        )
        proposal["index_updates"]["root_recent_entry"] = (
            f"- [[business/{chinese_slug}|贝佐斯如何学会拉拢特朗普并为蓝色起源狂揽合约]] (2026-07-04)"
        )
        raw_path = Path("2026-07-04-贝佐斯如何学会拉拢特朗普并为蓝色起源狂揽合约.md")
        proposal["source_file"] = f"newswiki/raw/{raw_path.name}"

        notes = normalize_proposal_slugs(proposal, raw_path)

        self.assertTrue(notes)
        self.assertRegex(proposal["article"]["slug"], r"^2026-07-04-article-[a-f0-9]{8}$")
        self.assertIn(proposal["article"]["slug"], proposal["article"]["path"])
        self.assertIn(proposal["article"]["slug"], proposal["index_updates"]["topic_index_entry"])
        self.assertNotIn(chinese_slug, proposal["article"]["path"])

    def test_enforce_canonical_topics_remaps_alias_slug(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["topic"]["slug"] = "ai-infrastructure"
        proposal["topic"]["path"] = "newswiki/wiki/ai-infrastructure"
        proposal["article"]["path"] = "newswiki/wiki/ai-infrastructure/2026-05-30-sample-article.md"
        proposal["article"]["topics"] = ["ai-infrastructure", "tech"]
        proposal["index_updates"]["root_recent_entry"] = (
            "- [[ai-infrastructure/2026-05-30-sample-article|Sample Article]] (2026-05-30)"
        )

        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            result = apply_proposal(proposal, raw_file, no_archive=True)

            self.assertEqual(result.action, "create_article")
            article_path = sync_module.ROOT / "newswiki/wiki/tech/2026-05-30-sample-article.md"
            self.assertTrue(article_path.exists())

    def test_enforce_canonical_topics_needs_review_for_unknown_slug(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["topic"]["slug"] = "quantum-computing"
        proposal["topic"]["path"] = "newswiki/wiki/quantum-computing"
        proposal["article"]["path"] = "newswiki/wiki/quantum-computing/2026-05-30-sample-article.md"

        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            result = apply_proposal(proposal, raw_file, no_archive=True)

            self.assertEqual(result.action, "needs_review")
            self.assertTrue(raw_file.exists())
            self.assertFalse(
                (sync_module.ROOT / "newswiki/wiki/quantum-computing/2026-05-30-sample-article.md").exists()
            )

            labeled = raw_file.read_text(encoding="utf-8")
            self.assertIn("sync_status:", labeled)
            self.assertIn("needs_review", labeled)
            self.assertIn("topic-not-canonical", labeled)
            self.assertIn('proposed_topic: "quantum-computing"', labeled)

            queue_path = sync_module.RAW_DIR / "REVIEW.md"
            self.assertTrue(queue_path.exists())
            queue_text = queue_path.read_text(encoding="utf-8")
            self.assertIn(raw_file.name, queue_text)
            self.assertIn("`topic-not-canonical`", queue_text)

    def test_scan_pending_files_skips_review_labeled_raw(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file("review-me.md", content="# pending review")
            mark_raw_needs_review(
                raw_file,
                labels=["topic-not-canonical"],
                notes=["Topic 'quantum-computing' is not canonical."],
                proposed_topic="quantum-computing",
            )

            self.assertEqual(scan_pending_files(), [])
            self.assertEqual(scan_pending_files(include_review=True), [raw_file])

    def test_validate_allows_skip_duplicate_without_article_fields(self) -> None:
        proposal = {
            "action": "skip_duplicate",
            "source_file": "newswiki/raw/2026-05-30-sample.md",
            "review_notes": ["Duplicate of existing wiki article."],
        }
        validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_normalize_wiki_path_prefixes_relative_paths(self) -> None:
        with sync_workspace():
            self.assertEqual(
                normalize_wiki_path("ai-infrastructure/sample.md"),
                "newswiki/wiki/ai-infrastructure/sample.md",
            )
            self.assertEqual(
                normalize_wiki_path("newswiki/wiki/ai-infrastructure/sample.md"),
                "newswiki/wiki/ai-infrastructure/sample.md",
            )
            self.assertEqual(
                normalize_wiki_path("sample.md", topic_slug="parenting"),
                "newswiki/wiki/parenting/sample.md",
            )

    def test_normalize_proposal_slugs_repairs_chinese_slug_from_source_url(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        chinese_slug = "巨额资金涌入AI，这是一个巨大的危险信号"
        expected_slug = "all-the-money-flooding-into-ai-is-a-giant-warning-sign-d71df439"
        proposal["article"]["slug"] = chinese_slug
        proposal["article"]["front_matter"]["source"] = (
            "https://cn.wsj.com/articles/all-the-money-flooding-into-ai-is-a-giant-warning-sign-d71df439"
        )
        proposal["article"]["path"] = f"newswiki/wiki/finance/{chinese_slug}.md"
        proposal["topic"]["slug"] = "finance"
        proposal["topic"]["path"] = "newswiki/wiki/finance"
        proposal["article"]["topics"] = ["finance"]
        proposal["index_updates"]["topic_index_entry"] = (
            f"- [[{chinese_slug}|巨额资金涌入AI]] (2026-06-24) - Summary"
        )
        proposal["index_updates"]["root_recent_entry"] = (
            f"- [[finance/{chinese_slug}|巨额资金涌入AI]] (2026-06-24)"
        )

        raw_path = Path("2026-06-24-巨额资金涌入AI，这是一个巨大的危险信号.md")
        proposal["source_file"] = f"newswiki/raw/{raw_path.name}"
        normalize_proposal_slugs(proposal, raw_path)
        normalize_proposal_paths(proposal)

        self.assertEqual(proposal["article"]["slug"], expected_slug)
        self.assertTrue(proposal["article"]["path"].endswith(f"{expected_slug}.md"))
        self.assertIn(f"[[{expected_slug}|", proposal["index_updates"]["topic_index_entry"])
        self.assertIn(f"finance/{expected_slug}|", proposal["index_updates"]["root_recent_entry"])
        validate_proposal(proposal, raw_path)

    def test_apply_proposal_prefixes_relative_article_path(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            proposal = copy.deepcopy(self.sample_proposal)
            proposal["article"]["path"] = "tech/2026-05-30-sample-article.md"
            proposal["topic"]["path"] = "tech"
            apply_proposal(proposal, raw_file, no_archive=True)

            article_path = sync_module.ROOT / proposal["article"]["path"]
            self.assertEqual(
                str(article_path.relative_to(sync_module.ROOT)),
                "newswiki/wiki/tech/2026-05-30-sample-article.md",
            )

    def test_apply_proposal_uses_raw_source_over_truncated_llm_url(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            proposal = copy.deepcopy(self.sample_proposal)
            proposal["article"]["front_matter"]["source"] = "https://cn.wsj.com/articles/..."
            apply_proposal(proposal, raw_file)

            article_path = sync_module.ROOT / proposal["article"]["path"]
            rendered = article_path.read_text(encoding="utf-8")
            self.assertIn('source: "https://example.com/sample"', rendered)
            self.assertIn("# [Sample Article](https://example.com/sample)", rendered)
            self.assertNotIn("articles/...", rendered)

    def test_render_fixture_article_markdown(self) -> None:
        rendered = render_article_markdown(self.sample_proposal)
        self.assertIn('title: "Sample Article"', rendered)
        self.assertIn("# [Sample Article](https://example.com/sample)", rendered)
        self.assertNotIn("**Source**:", rendered)
        self.assertIn("## Core View", rendered)
        self.assertIn("## Key Takeaways", rendered)
        self.assertIn("topics:", rendered)
        self.assertIn("**Topics**:", rendered)
        self.assertIn("[[tech/_index|Tech]]", rendered)
        self.assertIn("**Tags**: #tech #sample", rendered)

    def test_render_chinese_article_uses_chinese_labels(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["article"]["title"] = "示例文章"
        proposal["article"]["front_matter"]["title"] = "示例文章"
        proposal["article"]["front_matter"]["description"] = "中文描述"
        proposal["article"]["sections"][0]["heading"] = "核心观点"
        rendered = render_article_markdown(proposal)
        self.assertEqual(article_language(proposal["article"]), "zh")
        self.assertEqual(takeaways_heading("zh"), "核心要点")
        self.assertIn("## 核心要点", rendered)
        self.assertIn("**主题**:", rendered)
        self.assertIn("**标签**:", rendered)
        self.assertNotIn("## Key Takeaways", rendered)

    def test_normalize_proposal_language_resets_title_to_raw(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file("2026-06-02-sample-zh.md", content=self.chinese_raw)
            proposal = copy.deepcopy(self.sample_proposal)
            proposal["article"]["title"] = "Rewritten English Title"
            proposal["article"]["front_matter"]["title"] = "Rewritten English Title"
            proposal["index_updates"]["topic_index_entry"] = (
                "- [[2026-05-30-sample-article|Rewritten English Title]] (2026-05-30) - Summary"
            )
            proposal["index_updates"]["root_recent_entry"] = (
                "- [[tech/2026-05-30-sample-article|Rewritten English Title]] (2026-05-30)"
            )
            notes = normalize_proposal_language(proposal, raw_file)
            self.assertTrue(notes)
            self.assertEqual(proposal["article"]["title"], "示例文章")
            self.assertEqual(proposal["article"]["front_matter"]["title"], "示例文章")
            self.assertIn("示例文章", proposal["index_updates"]["topic_index_entry"])
            self.assertIn("示例文章", proposal["index_updates"]["root_recent_entry"])

    def test_update_indexes_from_fixture(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            (sync_module.WIKI_DIR / "business").mkdir(parents=True, exist_ok=True)
            (sync_module.WIKI_DIR / "business" / "_index.md").write_text(
                "# Business\n\n## 相关文章\n\n## 相关主题\n",
                encoding="utf-8",
            )
            proposal = copy.deepcopy(self.sample_proposal)
            proposal["article"]["topics"] = ["tech", "business"]
            update_indexes(proposal)

            tech_index = (sync_module.WIKI_DIR / "tech" / "_index.md").read_text(encoding="utf-8")
            business_index = (sync_module.WIKI_DIR / "business" / "_index.md").read_text(encoding="utf-8")
            root_index = sync_module.ROOT_INDEX.read_text(encoding="utf-8")
            self.assertIn("[[2026-05-30-sample-article|Sample Article]]", tech_index)
            self.assertIn("[[2026-05-30-sample-article|Sample Article]]", business_index)
            self.assertIn("[[tech/2026-05-30-sample-article|Sample Article]]", root_index)

    def test_build_status_row_uses_wiki_path(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file()
            row = build_status_row(self.sample_proposal, raw_file)
            self.assertIn("2026-05-30-sample.md", row)
            self.assertIn("Tech", row)
            self.assertIn("`newswiki/wiki/tech/2026-05-30-sample-article.md`", row)
            self.assertNotIn("https://example.com/sample", row)

    def test_append_status_row_from_fixture(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file()
            row = build_status_row(self.sample_proposal, raw_file)
            append_status_row(row)
            status = sync_module.STATUS_PATH.read_text(encoding="utf-8")
            self.assertIn("2026-05-30-sample.md", status)
            self.assertIn("Tech", status)
            self.assertIn("`newswiki/wiki/tech/2026-05-30-sample-article.md`", status)

    def test_apply_fixture_archives_raw_and_writes_article(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            result = apply_proposal(self.sample_proposal, raw_file)

            article_path = sync_module.ROOT / self.sample_proposal["article"]["path"]
            archived_path = sync_module.ARCHIVE_DIR / raw_file.name
            self.assertEqual(result.action, "create_article")
            self.assertTrue(result.archived)
            self.assertTrue(article_path.exists())
            self.assertFalse(raw_file.exists())
            self.assertTrue(archived_path.exists())
            archived_text = archived_path.read_text(encoding="utf-8")
            self.assertIn('source: "https://example.com/sample"', archived_text)
            self.assertNotIn("[[Company]]", archived_text)

    def test_apply_fixture_is_idempotent_for_indexes_and_status(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            apply_proposal(self.sample_proposal, raw_file)

            topic_index_after_first = (
                sync_module.WIKI_DIR / "tech" / "_index.md"
            ).read_text(encoding="utf-8")
            root_index_after_first = sync_module.ROOT_INDEX.read_text(encoding="utf-8")
            status_after_first = sync_module.STATUS_PATH.read_text(encoding="utf-8")

            append_status_row(build_status_row(self.sample_proposal, raw_file))
            update_indexes(self.sample_proposal)

            topic_index_after_second = (
                sync_module.WIKI_DIR / "tech" / "_index.md"
            ).read_text(encoding="utf-8")
            root_index_after_second = sync_module.ROOT_INDEX.read_text(encoding="utf-8")
            status_after_second = sync_module.STATUS_PATH.read_text(encoding="utf-8")

            self.assertEqual(topic_index_after_first, topic_index_after_second)
            self.assertEqual(root_index_after_first, root_index_after_second)
            self.assertEqual(status_after_first.count("2026-05-30-sample.md"), 1)
            self.assertEqual(status_after_second.count("2026-05-30-sample.md"), 1)

    def test_archive_source_is_idempotent(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file()
            archive_source(raw_file, self.sample_proposal)
            archive_source(raw_file, self.sample_proposal)
            archived_path = sync_module.ARCHIVE_DIR / raw_file.name
            self.assertTrue(archived_path.exists())
            self.assertIn("https://example.com/sample", archived_path.read_text(encoding="utf-8"))

    def test_remove_raw_source_deletes_inbox_file(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file()
            remove_raw_source(raw_file)
            self.assertFalse(raw_file.exists())

    def test_remove_raw_source_deletes_related_resources(self) -> None:
        with sync_workspace():
            resource_dir = sync_module.RESOURCES_DIR / "2026-05-30-sample"
            resource_dir.mkdir(parents=True)
            (resource_dir / "image_MD5.jpg").write_text("img", encoding="utf-8")
            raw_file = self._raw_file(
                content=self.sample_raw.replace(
                    "Raw article body",
                    "Raw article body\n\n![[_resources/2026-05-30-sample/image_MD5.jpg]]",
                )
            )
            remove_raw_source(raw_file)
            self.assertFalse(raw_file.exists())
            self.assertFalse(resource_dir.exists())

    def test_apply_proposal_no_archive_still_deletes_raw(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            result = apply_proposal(self.sample_proposal, raw_file, no_archive=True)
            self.assertEqual(result.action, "create_article")
            self.assertFalse(result.archived)
            self.assertFalse(raw_file.exists())
            self.assertFalse((sync_module.ARCHIVE_DIR / raw_file.name).exists())

    def test_apply_proposal_dry_run(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            result = apply_proposal(self.sample_proposal, raw_file, dry_run=True)
            self.assertEqual(result.action, "create_article")
            self.assertTrue(result.dry_run)
            self.assertFalse((sync_module.ROOT / self.sample_proposal["article"]["path"]).exists())

    def test_scan_pending_files_uses_cache(self) -> None:
        with sync_workspace():
            raw_file = self._raw_file("pending.md", content="# pending")
            pending = scan_pending_files()
            self.assertEqual([p.name for p in pending], ["pending.md"])

            sync_module.save_cache({"pending.md": sync_module._file_hash(raw_file)})
            pending_after = scan_pending_files()
            self.assertEqual(pending_after, [])

    def test_configure_paths_supports_custom_directories(self) -> None:
        with sync_workspace(source="research/raw", wiki="research/wiki"):
            self.assertEqual(sync_module.SOURCE_PREFIX, "research/raw")
            self.assertEqual(sync_module.WIKI_PREFIX, "research/wiki")

            proposal = copy.deepcopy(self.sample_proposal)
            proposal["source_file"] = "research/raw/2026-05-30-sample.md"
            proposal["topic"]["path"] = "research/wiki/ai-infrastructure"
            proposal["article"]["path"] = "research/wiki/ai-infrastructure/2026-05-30-sample-article.md"
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_run_sync_continues_after_file_error(self) -> None:
        with sync_workspace():
            results = [
                CompileResult(source_file="bad.md", action="error", errors=["boom"]),
                CompileResult(
                    source_file="good.md",
                    action="create_article",
                    article_path="newswiki/wiki/tech/good.md",
                ),
            ]

            with patch.object(sync_module, "sync_file", side_effect=results) as mock_sync:
                output = run_sync(
                    files=[Path("bad.md"), Path("good.md")],
                    provider=FixtureProvider({"action": "needs_review"}),
                )

            self.assertEqual(mock_sync.call_count, 2)
            self.assertEqual(len(output), 2)
            self.assertEqual(output[0].errors, ["boom"])
            self.assertEqual(output[1].action, "create_article")

    def test_summarize_sync_results_reports_failures(self) -> None:
        results = [
            CompileResult(source_file="bad.md", action="error", errors=["invalid JSON"]),
            CompileResult(source_file="good.md", action="create_article"),
        ]
        with sync_workspace():
            exit_code = summarize_sync_results(results)
            log_text = sync_module.SYNC_LOG_PATH.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 1)
        self.assertIn("FAILED: bad.md: invalid JSON", log_text)
        self.assertIn("processed=2 created=1", log_text)

    def test_sync_file_uses_injected_fixture_proposal(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            provider = FixtureProvider(self.sample_proposal)
            result = sync_module.sync_file(
                raw_file,
                provider,
                proposal=self.sample_proposal,
            )
            self.assertEqual(result.action, "create_article")
            self.assertEqual(len(provider.requests), 0)


class QueryWikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_response = load_query_fixture("sample_response.json")
        cls.question = cls.sample_response["question"]

    def _seed_topic_index(self) -> None:
        topic_dir = query_module.WIKI_DIR / "ai-infrastructure"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "_index.md").write_text(
            "# AI Infrastructure\n\n## 相关文章\n- [[2026-05-27-nebius-vs-coreweave|CoreWeave请让位，Nebius来了]]\n",
            encoding="utf-8",
        )

    def test_validate_fixture_query_response(self) -> None:
        validate_query_response(self.sample_response, self.question)

    def test_validate_rejects_question_mismatch(self) -> None:
        response = copy.deepcopy(self.sample_response)
        response["question"] = "Different question?"
        with self.assertRaisesRegex(ValueError, "question field"):
            validate_query_response(response, self.question)

    def test_validate_rejects_unlabeled_ai_synthesis(self) -> None:
        response = copy.deepcopy(self.sample_response)
        response["answer"]["sections"][0]["bullets"].append("AI Synthesis without label.")
        with self.assertRaisesRegex(ValueError, "AI Synthesis"):
            validate_query_response(response, self.question)

    def test_validate_rejects_bad_wiki_citation_path(self) -> None:
        response = copy.deepcopy(self.sample_response)
        response["citations"][0]["path"] = "research/wiki/wrong.md"
        with self.assertRaisesRegex(ValueError, "must live under"):
            validate_query_response(response, self.question)

    def test_render_fixture_query_markdown(self) -> None:
        rendered = render_query_markdown(self.sample_response)
        self.assertIn("# How does Nebius compare to CoreWeave?", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("## Competitive Comparison", rendered)
        self.assertIn("## Citations", rendered)
        self.assertIn("[[ai-infrastructure/2026-05-27-nebius-vs-coreweave|CoreWeave请让位，Nebius来了]]", rendered)
        self.assertIn("**external**:", rendered)

    def test_build_wiki_context_includes_indexes(self) -> None:
        with query_workspace():
            self._seed_topic_index()
            context = build_wiki_context()
            self.assertIn("Recent Articles", context)
            self.assertIn("AI Infrastructure", context)

    def test_build_query_prompt_includes_question_and_paths(self) -> None:
        with query_workspace(source="research/raw", wiki="research/wiki", outputs="research/outputs"):
            request = build_query_prompt(self.question)
            self.assertIn(self.question, request.prompt)
            self.assertIn("research/wiki/", request.prompt)
            self.assertIn("research/raw/", request.prompt)
            self.assertIn("Query contract", request.prompt)

    def test_save_query_output_writes_markdown(self) -> None:
        with query_workspace():
            saved = save_query_output(self.sample_response)
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertTrue(saved.exists())
            content = saved.read_text(encoding="utf-8")
            self.assertIn("## Citations", content)

    def test_run_query_uses_injected_fixture_response(self) -> None:
        with query_workspace():
            provider = FixtureProvider(self.sample_response)
            result = run_query(self.question, provider, response=self.sample_response)
            self.assertFalse(result.errors)
            self.assertTrue(result.saved)
            self.assertIsNotNone(result.output_path)

    def test_run_query_dry_run_does_not_save(self) -> None:
        with query_workspace():
            provider = FixtureProvider(self.sample_response)
            result = run_query(self.question, provider, dry_run=True, response=self.sample_response)
            self.assertFalse(result.errors)
            self.assertFalse(result.saved)
            self.assertEqual(len(list(query_module.OUTPUTS_DIR.glob("*.md"))), 0)

    def test_configure_paths_supports_custom_directories(self) -> None:
        with query_workspace(wiki="research/wiki", outputs="research/outputs", source="research/raw"):
            self.assertEqual(query_module.WIKI_PREFIX, "research/wiki")
            self.assertEqual(query_module.OUTPUTS_PREFIX, "research/outputs")
            self.assertEqual(query_module.SOURCE_PREFIX, "research/raw")

            response = copy.deepcopy(self.sample_response)
            response["citations"][0]["path"] = (
                "research/wiki/ai-infrastructure/2026-05-27-nebius-vs-coreweave.md"
            )
            response["citations"][1]["path"] = (
                "research/raw/archive/2026-05-27-CoreWeave请让位，Nebius来了.md"
            )
            validate_query_response(response, self.question)


class AuditWikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_response = load_audit_fixture("sample_response.json")

    def _seed_wiki_with_broken_link(self) -> None:
        topic_dir = audit_module.WIKI_DIR / "nvda"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "2026-05-21-nvda-undervalued.md").write_text(
            "# NVDA\n\nCompetes with [[Intel]] and [[OpenAI]].\n",
            encoding="utf-8",
        )
        audit_module.ROOT_INDEX.write_text(
            "## Philosophy\n- [[moats|护城河理论]]\n",
            encoding="utf-8",
        )

    def test_extract_wiki_links(self) -> None:
        content = "See [[Intel]] and [[nvda/2026-05-21-nvda-undervalued|NVDA article]]."
        links = extract_wiki_links(content)
        self.assertEqual(links, ["Intel", "nvda/2026-05-21-nvda-undervalued"])

    def test_resolve_existing_and_missing_links(self) -> None:
        with audit_workspace():
            self._seed_wiki_with_broken_link()
            article = audit_module.WIKI_DIR / "nvda" / "2026-05-21-nvda-undervalued.md"

            ok, reason = resolve_wiki_link("nvda/2026-05-21-nvda-undervalued", article)
            self.assertTrue(ok)
            self.assertIn("nvda/2026-05-21-nvda-undervalued.md", reason)

            ok, reason = resolve_wiki_link("Intel", article)
            self.assertFalse(ok)
            self.assertEqual(reason, "wiki target not found")

    def test_scan_broken_links_without_llm(self) -> None:
        with audit_workspace():
            self._seed_wiki_with_broken_link()
            broken = scan_broken_links()
            targets = {item.target for item in broken}
            self.assertIn("Intel", targets)
            self.assertIn("OpenAI", targets)
            self.assertIn("moats", {item.target for item in run_deterministic_checks().index_gaps})

    def test_validate_fixture_audit_response(self) -> None:
        validate_audit_response(self.sample_response)

    def test_validate_rejects_bad_severity(self) -> None:
        response = copy.deepcopy(self.sample_response)
        response["findings"][0]["severity"] = "urgent"
        with self.assertRaisesRegex(ValueError, "severity"):
            validate_audit_response(response)

    def test_validate_rejects_bad_wiki_evidence_path(self) -> None:
        response = copy.deepcopy(self.sample_response)
        response["findings"][0]["evidence"][0]["path"] = "research/wiki/wrong.md"
        with self.assertRaisesRegex(ValueError, "must live under"):
            validate_audit_response(response)

    def test_render_fixture_audit_markdown(self) -> None:
        rendered = render_audit_markdown(self.sample_response)
        self.assertIn("# Wiki Audit Report", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("## Findings", rendered)
        self.assertIn("Broken link to Intel in NVDA article", rendered)
        self.assertIn("## Coverage Gaps", rendered)
        self.assertIn("[[nvda/2026-05-21-nvda-undervalued|", rendered)

    def test_build_audit_prompt_includes_paths_and_findings(self) -> None:
        with audit_workspace(source="research/raw", wiki="research/wiki", outputs="research/outputs"):
            self._seed_wiki_with_broken_link()
            request = build_audit_prompt(run_deterministic_checks())
            self.assertIn("research/wiki/", request.prompt)
            self.assertIn("research/raw/", request.prompt)
            self.assertIn("Audit contract", request.prompt)
            self.assertIn("Broken links (harness)", request.prompt)

    def test_save_audit_output_writes_markdown(self) -> None:
        with audit_workspace():
            saved = save_audit_output(self.sample_response)
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertTrue(saved.exists())
            content = saved.read_text(encoding="utf-8")
            self.assertIn("## Findings", content)

    def test_run_audit_uses_injected_fixture_response(self) -> None:
        with audit_workspace():
            provider = FixtureProvider(self.sample_response)
            result = run_audit(provider, response=self.sample_response)
            self.assertFalse(result.errors)
            self.assertTrue(result.saved)
            self.assertIsNotNone(result.output_path)

    def test_run_audit_dry_run_does_not_save(self) -> None:
        with audit_workspace():
            provider = FixtureProvider(self.sample_response)
            result = run_audit(provider, dry_run=True, response=self.sample_response)
            self.assertFalse(result.errors)
            self.assertFalse(result.saved)
            self.assertEqual(len(list(audit_module.OUTPUTS_DIR.glob("*.md"))), 0)

    def test_configure_paths_supports_custom_directories(self) -> None:
        with audit_workspace(wiki="research/wiki", outputs="research/outputs", source="research/raw"):
            self.assertEqual(audit_module.WIKI_PREFIX, "research/wiki")
            self.assertEqual(audit_module.OUTPUTS_PREFIX, "research/outputs")
            self.assertEqual(audit_module.SOURCE_PREFIX, "research/raw")

            response = copy.deepcopy(self.sample_response)
            response["findings"][0]["evidence"][0]["path"] = (
                "research/wiki/nvda/2026-05-21-nvda-undervalued.md"
            )
            response["findings"][1]["evidence"][0]["path"] = "research/wiki/INDEX.md"
            validate_audit_response(response)


class LLMProviderTests(unittest.TestCase):
    def test_fixture_provider_returns_json_proposal(self) -> None:
        fixture = {
            "action": "create_article",
            "source_file": "newswiki/raw/example.md",
            "review_notes": [],
        }
        provider = FixtureProvider(fixture)
        request = LLMRequest(system="compile rules", prompt="raw article")

        proposal = proposal_from_provider(provider, request)

        self.assertEqual(proposal["action"], "create_article")
        self.assertEqual(provider.requests, [request])

    def test_provider_factory_accepts_fixture(self) -> None:
        provider = build_provider("fixture", fixture={"action": "needs_review"})

        proposal = proposal_from_provider(provider, LLMRequest(system="", prompt=""))

        self.assertEqual(proposal["action"], "needs_review")

    def test_invalid_fixture_json_is_rejected(self) -> None:
        provider = FixtureProvider("not json")

        with self.assertRaisesRegex(ValueError, "invalid JSON after"):
            proposal_from_provider(provider, LLMRequest(system="", prompt=""))
        self.assertEqual(len(provider.requests), 2)

    def test_proposal_from_provider_retries_invalid_json(self) -> None:
        class FlakyProvider:
            def __init__(self) -> None:
                self.requests: list[LLMRequest] = []

            def complete(self, request: LLMRequest) -> str:
                self.requests.append(request)
                if len(self.requests) == 1:
                    return "not json"
                return '{"action": "needs_review", "review_notes": []}'

        provider = FlakyProvider()
        request = LLMRequest(system="rules", prompt="compile this")

        proposal = proposal_from_provider(provider, request)

        self.assertEqual(proposal["action"], "needs_review")
        self.assertEqual(len(provider.requests), 2)
        self.assertIn(JSON_RETRY_PROMPT, provider.requests[1].prompt)

    def test_openai_compatible_provider_defaults(self) -> None:
        provider = OpenAICompatibleProvider(provider="mlx")
        self.assertEqual(provider.temperature, resolve_temperature())
        self.assertEqual(provider.max_tokens, resolve_max_tokens())
        self.assertEqual(resolve_temperature(), 0.0)
        self.assertEqual(resolve_max_tokens(), 4096)

    def test_extract_json_object_accepts_fenced_json(self) -> None:
        payload = extract_json_object(
            '```json\n{"action": "needs_review", "review_notes": []}\n```'
        )
        self.assertEqual(payload["action"], "needs_review")

    def test_provider_factory_accepts_mlx(self) -> None:
        provider = build_provider("mlx")
        self.assertEqual(provider.provider, "mlx")

    def test_provider_factory_accepts_gemini(self) -> None:
        provider = build_provider("gemini")
        self.assertIn(provider.provider, {"gemini", "mlx"})

    def test_default_provider_prefers_mlx(self) -> None:
        # Load tests must remain deterministic even when a developer .env exists.
        with patch.dict("os.environ", {"LLM_PROVIDER": "mlx"}, clear=False):
            self.assertEqual(default_provider(), "mlx")

    def test_resolve_model_uses_gemini_env(self) -> None:
        with patch.dict(
            "os.environ",
            {"GEMINI_MODEL": "gemini-2.5-flash-lite"},
            clear=False,
        ):
            self.assertEqual(resolve_model("gemini"), "gemini-2.5-flash-lite")

    def test_fallback_chain_gemini_then_mlx(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "LLM_FALLBACK_ENABLED": "1",
            },
            clear=False,
        ):
            self.assertEqual(fallback_provider_chain("gemini"), ["gemini", "mlx"])

    def test_fallback_provider_uses_secondary_on_primary_failure(self) -> None:
        class FailingProvider:
            provider = "gemini"

            def complete(self, request: LLMRequest) -> str:
                raise RuntimeError("gemini unavailable")

        class SuccessProvider:
            provider = "mlx"

            def complete(self, request: LLMRequest) -> str:
                return '{"action": "needs_review", "review_notes": []}'

        provider = FallbackProvider(
            [FailingProvider(), SuccessProvider()],
            ["gemini", "mlx"],
        )
        proposal = proposal_from_provider(provider, LLMRequest(system="", prompt=""))
        self.assertEqual(proposal["action"], "needs_review")

    def test_gemini_provider_requires_api_key(self) -> None:
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
            provider = GeminiProvider()
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                provider.complete(LLMRequest(system="", prompt="test"))


class ZhConvertTests(unittest.TestCase):
    def test_convert_visible_text_to_traditional(self) -> None:
        converted = convert_visible_text("简体中文与芯片投资")
        self.assertIn("簡體中文", converted)
        self.assertIn("芯片", converted)

    def test_convert_markdown_preserves_wiki_paths(self) -> None:
        source = "# [[personal-finance/article|个人理财]]\n\n投资与传承。"
        converted = convert_markdown(source)
        self.assertIn("[[personal-finance/article|", converted)
        self.assertIn("個人理財", converted)
        self.assertIn("投資", converted)

    def test_convert_markdown_preserves_source_url(self) -> None:
        source = (
            '---\ntitle: "示例文章"\nsource: "https://example.com/sample"\n---\n\n'
            "正文内容。"
        )
        converted = convert_markdown(source)
        self.assertIn('source: "https://example.com/sample"', converted)
        self.assertIn("正文內容", converted)


class PrepareQuartzContentTests(unittest.TestCase):
    def test_trim_recent_articles_for_site_limits_homepage(self) -> None:
        entries = [
            f"- [[topic/article-{index}|Article {index}]] (2026-06-{index:02d})"
            for index in range(1, 8)
        ]
        index_content = "# News Wiki\n\n## Recent Articles\n\n" + "\n".join(entries) + "\n\n## Philosophy\n"
        trimmed, all_entries = trim_recent_articles_for_site(index_content)

        self.assertEqual(len(all_entries), 7)
        visible_entries = prepare_module._collect_recent_article_entries(trimmed)
        self.assertEqual(len(visible_entries), prepare_module.RECENT_ARTICLES_LIMIT)
        self.assertIn("[[articles|More]]", trimmed)

    def test_prepare_content_writes_articles_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wiki_dir = tmp_path / "wiki"
            content_dir = tmp_path / "content"
            wiki_dir.mkdir()
            entries = [
                f"- [[topic/article-{index}|Article {index}]] (2026-06-{index:02d})"
                for index in range(1, 8)
            ]
            (wiki_dir / "INDEX.md").write_text(
                "# News Wiki\n\n## Recent Articles\n\n" + "\n".join(entries) + "\n",
                encoding="utf-8",
            )

            prepare_content(wiki_dir, content_dir)

            site_index = (content_dir / "index.md").read_text(encoding="utf-8")
            visible_entries = prepare_module._collect_recent_article_entries(site_index)
            self.assertEqual(len(visible_entries), prepare_module.RECENT_ARTICLES_LIMIT)
            self.assertIn("[[articles|More]]", site_index)

            all_articles = (content_dir / "articles.md").read_text(encoding="utf-8")
            self.assertEqual(len(prepare_module._collect_article_entries_from_text(all_articles)), 7)
            self.assertFalse((wiki_dir / "articles.md").exists())

    def test_trim_topics_groups_for_site_limits_each_group(self) -> None:
        entries = [
            f"- [[topic-{index}|Topic {index}]]: summary {index}."
            for index in range(1, 8)
        ]
        index_content = (
            "# News Wiki\n\n## Topics\n\n### Tech & Infrastructure\n\n"
            + "\n".join(entries)
            + "\n\n## Recent Articles\n"
        )
        trimmed = trim_topics_groups_for_site(index_content)
        group_section = trimmed.split("### Tech & Infrastructure", 1)[1].split("## Recent Articles", 1)[0]
        visible_entries = prepare_module._collect_list_entries(group_section.splitlines())
        self.assertEqual(len(visible_entries), prepare_module.TOPICS_DISPLAY_LIMIT)
        self.assertIn("[[articles|More]]", group_section)

    def test_trim_related_articles_for_site_limits_topic_index(self) -> None:
        entries = [
            f"- [[article-{index}|Article {index}]] (2026-06-{index:02d}) - summary."
            for index in range(1, 8)
        ]
        topic_index = "# Topic\n\n## 相关文章\n\n" + "\n".join(entries) + "\n\n## 相关主题\n"
        trimmed = trim_related_articles_for_site(topic_index)
        related_section = trimmed.split("## 相关文章", 1)[1].split("## 相关主题", 1)[0]
        visible_entries = prepare_module._collect_list_entries(related_section.splitlines())
        self.assertEqual(len(visible_entries), prepare_module.RECENT_ARTICLES_LIMIT)
        self.assertIn("[[articles|More]]", related_section)

    def test_prepare_content_trims_topic_index_articles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wiki_dir = tmp_path / "wiki"
            content_dir = tmp_path / "content"
            topic_dir = wiki_dir / "ai-employment"
            topic_dir.mkdir(parents=True)
            entries = [
                f"- [[article-{index}|Article {index}]] (2026-06-{index:02d}) - summary."
                for index in range(1, 8)
            ]
            (topic_dir / "_index.md").write_text(
                "# AI & Employment\n\n## 相关文章\n\n" + "\n".join(entries) + "\n",
                encoding="utf-8",
            )
            (wiki_dir / "INDEX.md").write_text("# News Wiki\n\n## Recent Articles\n", encoding="utf-8")

            prepare_content(wiki_dir, content_dir)

            site_topic_index = (content_dir / "ai-employment" / "index.md").read_text(encoding="utf-8")
            related_section = site_topic_index.split("## 相關文章", 1)[1]
            visible_entries = prepare_module._collect_list_entries(related_section.splitlines())
            self.assertEqual(len(visible_entries), prepare_module.RECENT_ARTICLES_LIMIT)
            self.assertIn("[[articles|More]]", related_section)


class DensifyWikiTests(unittest.TestCase):
    def test_strip_related_preserves_topics_footer(self) -> None:
        from wiki.densify import _strip_existing_related, upsert_related_section, Article
        from pathlib import Path

        sample = (
            "# T\n\n## 核心观点\n- hi\n\n## 相关文章\n\n"
            "- [[business/a|A]]\n\n---\n**Topics**: [[business/_index|Business]]  \n"
            "**Tags**: #business\n"
        )
        stripped = _strip_existing_related(sample)
        self.assertIn("**Topics**", stripped)
        self.assertNotIn("相关文章", stripped)

        related = [
            Article(Path("x"), "business/c.md", "business/c", "C", ["business"]),
        ]
        out = upsert_related_section(sample, related)
        self.assertIn("**Topics**", out)
        self.assertIn("[[business/c|C]]", out)


if __name__ == "__main__":
    unittest.main()
