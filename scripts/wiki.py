#!/usr/bin/env python3
"""Unified CLI for wiki harness operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki.py",
        description="Wiki harness: sync, query, audit, site prep, and maintenance.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync", help="Sync raw markdown into structured wiki articles.")
    subparsers.add_parser("query", help="Query the investment wiki with LLM synthesis.")
    subparsers.add_parser("audit", help="Audit the investment wiki for link and coverage issues.")
    subparsers.add_parser("site-prepare", help="Copy wiki content into the Quartz site folder.")
    subparsers.add_parser("rebuild-indexes", help="Rebuild topic _index.md from article front matter.")
    subparsers.add_parser("backfill-sources", help="Repair wiki articles with truncated source URLs.")
    subparsers.add_parser("backfill-titles", help="Link wiki H1 titles to source URLs.")
    subparsers.add_parser(
        "densify-links",
        help="Add related-article cross-links and entity hubs for denser backlinks.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _build_parser().print_help()
        return 0

    command = argv[0]
    rest = argv[1:]

    if command == "sync":
        from wiki.sync import main as sync_main

        sys.argv = ["wiki sync", *rest]
        return sync_main()

    if command == "query":
        from wiki.query import main as query_main

        sys.argv = ["wiki query", *rest]
        return query_main()

    if command == "audit":
        from wiki.audit import main as audit_main

        sys.argv = ["wiki audit", *rest]
        return audit_main()

    if command == "site-prepare":
        from wiki.site import main as site_main

        sys.argv = ["wiki site-prepare", *rest]
        site_main()
        return 0

    if command == "rebuild-indexes":
        from wiki.indexes import main as rebuild_main

        sys.argv = ["wiki rebuild-indexes", *rest]
        rebuild_main()
        return 0

    if command == "backfill-sources":
        from wiki.sync import backfill_wiki_sources, configure_paths

        backfill_parser = argparse.ArgumentParser(add_help=False)
        backfill_parser.add_argument("--source", default="newswiki/raw")
        backfill_parser.add_argument("--wiki", default="newswiki/wiki")
        backfill_parser.add_argument("--archive", default=None)
        args, _ = backfill_parser.parse_known_args(rest)
        configure_paths(
            source=args.source,
            wiki=args.wiki,
            archive=args.archive or f"{args.source}/archive",
        )
        updated = backfill_wiki_sources()
        if not updated:
            print("[wiki] no wiki sources to backfill.")
            return 0
        for rel_path in updated:
            print(f"[wiki] backfilled source: {rel_path}")
        return 0

    if command == "backfill-titles":
        from wiki.sync import backfill_wiki_source_titles, configure_paths

        backfill_parser = argparse.ArgumentParser(add_help=False)
        backfill_parser.add_argument("--source", default="newswiki/raw")
        backfill_parser.add_argument("--wiki", default="newswiki/wiki")
        backfill_parser.add_argument("--archive", default=None)
        args, _ = backfill_parser.parse_known_args(rest)
        configure_paths(
            source=args.source,
            wiki=args.wiki,
            archive=args.archive or f"{args.source}/archive",
        )
        updated = backfill_wiki_source_titles()
        if not updated:
            print("[wiki] no wiki titles to backfill.")
            return 0
        for rel_path in updated:
            print(f"[wiki] backfilled title: {rel_path}")
        return 0

    if command == "densify-links":
        from wiki.densify import main as densify_main

        return densify_main(rest)

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
