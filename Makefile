# dev.money automation

PYTHON = python3
SOURCE ?= business/raw
WIKI ?= business/wiki
ARCHIVE ?= $(SOURCE)/archive
OUTPUTS ?= business/outputs
SITE_DIR ?= site
SITE_CONTENT ?= $(SITE_DIR)/content
SITE_OUTPUT ?= $(SITE_DIR)/public
SITE_PORT ?= 8080
PAGES_PROJECT ?= business
SYNC_FLAGS = --source "$(SOURCE)" --wiki "$(WIKI)" --archive "$(ARCHIVE)"
QUERY_FLAGS = --wiki "$(WIKI)" --outputs "$(OUTPUTS)" --source "$(SOURCE)"
AUDIT_FLAGS = --wiki "$(WIKI)" --source "$(SOURCE)" --outputs "$(OUTPUTS)"

.PHONY: help test sync sync-dry-run sync-all sync-no-archive sync-file compile compile-dry-run compile-all compile-no-archive compile-file query query-dry-run audit audit-dry-run analyze site-prepare site-install site-build site-serve site-deploy

help:
	@echo "dev.money Commands:"
	@echo "  make test              - Run unit and pipeline tests"
	@echo "  make sync              - Sync pending source files into wiki (default: business/raw -> business/wiki)"
	@echo "  make sync-dry-run      - Validate sync plan without writing files"
	@echo "  make sync-all          - Re-sync including cached source files"
	@echo "  make sync-no-archive   - Write wiki output but keep source files in place"
	@echo "  make sync-file FILE=name.md - Sync one source file"
	@echo "  make query QUESTION=\"...\" - Query wiki and save answer to outputs"
	@echo "  make query-dry-run QUESTION=\"...\" - Validate query plan without saving"
	@echo "  make audit             - Audit wiki quality and save report to outputs"
	@echo "  make audit-dry-run     - Validate audit plan without saving"
	@echo "  make analyze TICKER=MSFT - Run stock analysis pipeline"
	@echo "  make site-build        - Build Quartz website from business/wiki"
	@echo "  make site-serve        - Preview Quartz website locally"
	@echo "  make site-deploy       - Deploy site/public to Cloudflare Pages"
	@echo ""
	@echo "Path overrides:"
	@echo "  make sync SOURCE=research/raw WIKI=research/wiki"
	@echo "  make query WIKI=research/wiki OUTPUTS=research/outputs SOURCE=research/raw QUESTION=\"...\""
	@echo "  make audit WIKI=research/wiki SOURCE=research/raw OUTPUTS=research/outputs"
	@echo "  make site-build WIKI=research/wiki SITE_DIR=site"

test:
	$(PYTHON) scripts/test_suite.py

sync:
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS)

sync-dry-run:
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS) --dry-run

sync-all:
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS) --all

sync-no-archive:
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS) --no-archive

sync-file:
	@test -n "$(FILE)" || (echo "Usage: make sync-file FILE=2026-05-30-sample.md"; exit 1)
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS) --file "$(FILE)"

compile: sync
compile-dry-run: sync-dry-run
compile-all: sync-all
compile-no-archive: sync-no-archive
compile-file: sync-file

query:
	@test -n "$(QUESTION)" || (echo 'Usage: make query QUESTION="How does Nebius compare to CoreWeave?"'; exit 1)
	$(PYTHON) scripts/query_wiki.py $(QUERY_FLAGS) --question "$(QUESTION)"

query-dry-run:
	@test -n "$(QUESTION)" || (echo 'Usage: make query-dry-run QUESTION="How does Nebius compare to CoreWeave?"'; exit 1)
	$(PYTHON) scripts/query_wiki.py $(QUERY_FLAGS) --question "$(QUESTION)" --dry-run

audit:
	$(PYTHON) scripts/audit_wiki.py $(AUDIT_FLAGS)

audit-dry-run:
	$(PYTHON) scripts/audit_wiki.py $(AUDIT_FLAGS) --dry-run

analyze:
	@test -n "$(TICKER)" || (echo "Usage: make analyze TICKER=MSFT"; exit 1)
	$(PYTHON) scripts/analyze.py "$(TICKER)"

site-prepare:
	$(PYTHON) scripts/prepare_quartz_content.py --wiki "$(WIKI)" --content "$(SITE_CONTENT)"

site-install:
	cd "$(SITE_DIR)" && npm install

site-build: site-prepare
	cd "$(SITE_DIR)" && npm run quartz -- build --output "$(abspath $(SITE_OUTPUT))"

site-serve: site-prepare
	cd "$(SITE_DIR)" && npm run quartz -- build --serve --port "$(SITE_PORT)" --output "$(abspath $(SITE_OUTPUT))"

site-deploy: site-build
	npx wrangler pages deploy "$(SITE_OUTPUT)" --project-name "$(PAGES_PROJECT)"
