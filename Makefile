# dev.business automation

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
DRY_RUN ?=
ALL ?=
NO_ARCHIVE ?=
FILE ?=
SYNC_EXTRA_FLAGS = $(if $(DRY_RUN),--dry-run) $(if $(ALL),--all) $(if $(NO_ARCHIVE),--no-archive) $(if $(FILE),--file "$(FILE)")
QUERY_EXTRA_FLAGS = $(if $(DRY_RUN),--dry-run)
AUDIT_EXTRA_FLAGS = $(if $(DRY_RUN),--dry-run)

.PHONY: help test sync sync-dry-run sync-all sync-no-archive sync-file compile compile-dry-run compile-all compile-no-archive compile-file query query-dry-run audit audit-dry-run analyze site-prepare site-install site-build site-serve site-deploy

help:
	@echo "dev.business Commands:"
	@echo "  make test              - Run unit and pipeline tests"
	@echo "  make sync              - Sync source files into wiki"
	@echo "  make query QUESTION=\"...\" - Query wiki and save answer to outputs"
	@echo "  make audit             - Audit wiki quality and save report to outputs"
	@echo "  make analyze TICKER=MSFT - Run stock analysis pipeline"
	@echo "  make site-build        - Build Quartz website from business/wiki"
	@echo "  make site-serve        - Preview Quartz website locally"
	@echo "  make site-deploy       - Deploy site/public to Cloudflare Pages"
	@echo ""
	@echo "Common options:"
	@echo "  DRY_RUN=1, ALL=1, NO_ARCHIVE=1, FILE=name.md"
	@echo "  Example: make sync DRY_RUN=1"
	@echo ""
	@echo "Path overrides:"
	@echo "  make sync SOURCE=research/raw WIKI=research/wiki"
	@echo "  make query WIKI=research/wiki OUTPUTS=research/outputs SOURCE=research/raw QUESTION=\"...\""
	@echo "  make audit WIKI=research/wiki SOURCE=research/raw OUTPUTS=research/outputs"
	@echo "  make site-build WIKI=research/wiki SITE_DIR=site"
	@echo ""
	@echo "Compatibility aliases (still supported):"
	@echo "  make sync-dry-run | sync-all | sync-no-archive | sync-file FILE=..."
	@echo "  make compile | compile-dry-run | compile-all | compile-no-archive | compile-file FILE=..."
	@echo "  make query-dry-run QUESTION=\"...\" | audit-dry-run"

test:
	$(PYTHON) scripts/test_suite.py

sync:
	$(PYTHON) scripts/sync_wiki.py $(SYNC_FLAGS) $(SYNC_EXTRA_FLAGS)

sync-dry-run:
	@$(MAKE) sync DRY_RUN=1

sync-all:
	@$(MAKE) sync ALL=1

sync-no-archive:
	@$(MAKE) sync NO_ARCHIVE=1

sync-file:
	@test -n "$(FILE)" || (echo "Usage: make sync-file FILE=2026-05-30-sample.md"; exit 1)
	@$(MAKE) sync FILE="$(FILE)"

compile: sync
compile-dry-run: sync-dry-run
compile-all: sync-all
compile-no-archive: sync-no-archive
compile-file: sync-file

query:
	@test -n "$(QUESTION)" || (echo 'Usage: make query QUESTION="How does Nebius compare to CoreWeave?"'; exit 1)
	$(PYTHON) scripts/query_wiki.py $(QUERY_FLAGS) --question "$(QUESTION)" $(QUERY_EXTRA_FLAGS)

query-dry-run:
	@test -n "$(QUESTION)" || (echo 'Usage: make query-dry-run QUESTION="How does Nebius compare to CoreWeave?"'; exit 1)
	@$(MAKE) query QUESTION="$(QUESTION)" DRY_RUN=1

audit:
	$(PYTHON) scripts/audit_wiki.py $(AUDIT_FLAGS) $(AUDIT_EXTRA_FLAGS)

audit-dry-run:
	@$(MAKE) audit DRY_RUN=1

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
