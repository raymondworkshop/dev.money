"""Integrated unit + pipeline tests for dev.money scripts."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from evaluator import evaluate
from ingestion import fetch_financial_report, read_raw_report
import sync_wiki as sync_module
from sync_wiki import (
    apply_proposal,
    append_status_row,
    archive_source,
    configure_paths,
    parse_raw_front_matter,
    render_article_markdown,
    scan_pending_files,
    sync_file,
    update_indexes,
    validate_proposal,
)
from llm_provider import FixtureProvider, LLMRequest, build_provider, proposal_from_provider
from metrics import free_cash_flow, operating_margin, peg_ratio, revenue_growth
from parser import parse_report
import query_wiki as query_module
from query_wiki import (
    build_query_prompt,
    build_wiki_context,
    configure_paths,
    render_query_markdown,
    run_query,
    save_query_output,
    validate_query_response,
)
import audit_wiki as audit_module
from audit_wiki import (
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
from reporter import build_markdown, write_report


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
    source: str = "business/raw",
    wiki: str = "business/wiki",
    archive: str | None = None,
):
    """Patch sync_wiki paths to an isolated temp workspace."""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        original = {
            "ROOT": sync_module.ROOT,
            "RAW_DIR": sync_module.RAW_DIR,
            "ARCHIVE_DIR": sync_module.ARCHIVE_DIR,
            "WIKI_DIR": sync_module.WIKI_DIR,
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
        sync_module.ROOT_INDEX.write_text("## Recent Articles\n", encoding="utf-8")

        try:
            yield tmp_path
        finally:
            for key, value in original.items():
                setattr(sync_module, key, value)


@contextmanager
def query_workspace(
    *,
    wiki: str = "business/wiki",
    outputs: str = "business/outputs",
    source: str = "business/raw",
):
    """Patch query_wiki paths to an isolated temp workspace."""

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
    wiki: str = "business/wiki",
    outputs: str = "business/outputs",
    source: str = "business/raw",
):
    """Patch audit_wiki paths to an isolated temp workspace."""

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
        topic_dir = sync_module.WIKI_DIR / "ai-infrastructure"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "_index.md").write_text(
            "# AI Infrastructure\n\n## 相关文章\n",
            encoding="utf-8",
        )

    def _raw_file(self, name: str = "2026-05-30-sample.md", content: str | None = None) -> Path:
        raw_file = sync_module.RAW_DIR / name
        raw_file.write_text(content or self.sample_raw, encoding="utf-8")
        return raw_file

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
        proposal["source_file"] = "business/raw/wrong.md"
        with self.assertRaisesRegex(ValueError, "source_file"):
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_validate_rejects_unlabeled_ai_synthesis(self) -> None:
        proposal = copy.deepcopy(self.sample_proposal)
        proposal["article"]["sections"][0]["bullets"].append("AI Synthesis without label.")
        with self.assertRaisesRegex(ValueError, "AI Synthesis"):
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_validate_allows_skip_duplicate_without_article_fields(self) -> None:
        proposal = {
            "action": "skip_duplicate",
            "source_file": "business/raw/2026-05-30-sample.md",
            "review_notes": ["Duplicate of existing wiki article."],
        }
        validate_proposal(proposal, Path("2026-05-30-sample.md"))

    def test_render_fixture_article_markdown(self) -> None:
        rendered = render_article_markdown(self.sample_proposal)
        self.assertIn('title: "Sample Article"', rendered)
        self.assertIn("# Sample Article", rendered)
        self.assertIn("## Core View", rendered)
        self.assertIn("## Key Takeaways", rendered)
        self.assertIn("**Topic**: [[ai-infrastructure/_index|AI Infrastructure]]", rendered)
        self.assertIn("**Tags**: #ai-infrastructure #sample", rendered)

    def test_update_indexes_from_fixture(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            update_indexes(self.sample_proposal)

            topic_index = (sync_module.WIKI_DIR / "ai-infrastructure" / "_index.md").read_text(
                encoding="utf-8"
            )
            root_index = sync_module.ROOT_INDEX.read_text(encoding="utf-8")
            self.assertIn("[[2026-05-30-sample-article|Sample Article]]", topic_index)
            self.assertIn("## 相关文章", topic_index)
            self.assertIn("[[ai-infrastructure/2026-05-30-sample-article|Sample Article]]", root_index)

    def test_append_status_row_from_fixture(self) -> None:
        with sync_workspace():
            row = self.sample_proposal["archive"]["status_row"]
            append_status_row(row)
            status = sync_module.STATUS_PATH.read_text(encoding="utf-8")
            self.assertIn("2026-05-30-sample.md", status)
            self.assertIn("AI Infrastructure", status)

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

    def test_apply_fixture_is_idempotent_for_indexes_and_status(self) -> None:
        with sync_workspace():
            self._seed_topic_index()
            raw_file = self._raw_file()
            apply_proposal(self.sample_proposal, raw_file)

            topic_index_after_first = (
                sync_module.WIKI_DIR / "ai-infrastructure" / "_index.md"
            ).read_text(encoding="utf-8")
            root_index_after_first = sync_module.ROOT_INDEX.read_text(encoding="utf-8")
            status_after_first = sync_module.STATUS_PATH.read_text(encoding="utf-8")

            append_status_row(self.sample_proposal["archive"]["status_row"])
            update_indexes(self.sample_proposal)

            topic_index_after_second = (
                sync_module.WIKI_DIR / "ai-infrastructure" / "_index.md"
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
            archive_source(raw_file)
            archive_source(sync_module.ARCHIVE_DIR / raw_file.name)
            self.assertFalse(raw_file.exists())
            self.assertTrue((sync_module.ARCHIVE_DIR / raw_file.name).exists())

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
            proposal["archive"]["status_row"] = proposal["archive"]["status_row"].replace(
                "business/wiki", "research/wiki"
            )
            validate_proposal(proposal, Path("2026-05-30-sample.md"))

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
            "source_file": "business/raw/example.md",
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

        with self.assertRaises(ValueError):
            proposal_from_provider(provider, LLMRequest(system="", prompt=""))


if __name__ == "__main__":
    unittest.main()
