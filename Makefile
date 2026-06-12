# dev.business automation

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHONPATH := $(CURDIR)/scripts
export PYTHONPATH

LLM_PROVIDER ?= mlx
SOURCE ?= newswiki/raw
WIKI ?= newswiki/wiki
ARCHIVE ?= $(SOURCE)/archive
OUTPUTS ?= newswiki/outputs
SITE_DIR ?= site
SITE_CONTENT ?= $(SITE_DIR)/content
SITE_OUTPUT ?= $(SITE_DIR)/public
SITE_PORT ?= 8080
PAGES_PROJECT ?= news-wiki
PAGES_BRANCH ?= master
PAGES_URL ?= https://news-wiki.pages.dev/
DRY_RUN ?=
ALL ?=
REVIEW ?=
NO_ARCHIVE ?=
FILE ?=
QUESTION ?=
TICKER ?=
DEPLOY ?=
ACTION ?= install

RUN := $(PYTHON) scripts
PATH_FLAGS = --source "$(SOURCE)" --wiki "$(WIKI)"
SYNC_FLAGS = $(PATH_FLAGS) --archive "$(ARCHIVE)"
QUERY_FLAGS = $(PATH_FLAGS) --outputs "$(OUTPUTS)"
AUDIT_FLAGS = $(PATH_FLAGS) --outputs "$(OUTPUTS)"
SYNC_EXTRA = $(if $(DRY_RUN),--dry-run) $(if $(ALL),--all) $(if $(REVIEW),--include-review) $(if $(NO_ARCHIVE),--no-archive) $(if $(FILE),--file "$(FILE)") --provider "$(LLM_PROVIDER)"
LLM_EXTRA = $(if $(DRY_RUN),--dry-run) --provider "$(LLM_PROVIDER)"

.DEFAULT_GOAL := help
.PHONY: help test venv sync query audit analyze publish \
	site site-prepare site-install site-build site-serve site-deploy \
	rebuild-indexes backfill-sources backfill-titles launchd

help:
	@echo "dev.business"
	@echo ""
	@echo "Core:"
	@echo "  make test"
	@echo "  make sync              raw -> wiki"
	@echo "  make query QUESTION=\"...\""
	@echo "  make audit"
	@echo "  make analyze TICKER=MSFT"
	@echo "  make publish           sync + build + deploy (MLX)"
	@echo "  make site              build Quartz site"
	@echo ""
	@echo "Wiki maintenance:"
	@echo "  make rebuild-indexes   rebuild topic _index.md from article front matter"
	@echo "  make backfill-sources  repair truncated wiki source URLs"
	@echo "  make backfill-titles   link wiki H1 titles to source URLs"
	@echo ""
	@echo "Automation:"
	@echo "  make launchd           install weekly publish LaunchAgent"
	@echo "  make venv              create .venv and install requirements"
	@echo ""
	@echo "Options (append to sync/query/audit/publish):"
	@echo "  DRY_RUN=1              validate without writing"
	@echo "  ALL=1                  include cached sync files"
	@echo "  REVIEW=1               re-process raw files labeled needs_review"
	@echo "  NO_ARCHIVE=1           sync without archiving raw"
	@echo "  FILE=name.md           sync one raw file"
	@echo "  LLM_PROVIDER=gemini    cloud LLM (falls back to MLX on failure)"
	@echo "  LLM_PROVIDER=openai    cloud LLM instead of local MLX"
	@echo ""
	@echo "Site options:"
	@echo "  SERVE=1                local preview on SITE_PORT"
	@echo "  DEPLOY=1               build + deploy to Cloudflare"
	@echo "  DEPLOY=0               publish: sync only, skip deploy"
	@echo ""
	@echo "LaunchAgent: ACTION=unload|test"
	@echo "Paths: SOURCE= WIKI= ARCHIVE= OUTPUTS= SITE_DIR="

test:
	$(RUN)/test_suite.py

venv:
	@test -x .venv/bin/python || python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

sync:
	@mkdir -p logs
	@echo "=== sync $$(date -Iseconds) LLM_PROVIDER=$(LLM_PROVIDER) ===" | tee -a logs/sync.log
	@$(RUN)/wiki.py sync $(SYNC_FLAGS) $(SYNC_EXTRA) 2>&1 | tee -a logs/sync.log; exit $${PIPESTATUS[0]}

query:
	@test -n "$(QUESTION)" || (echo 'Usage: make query QUESTION="..."'; exit 1)
	$(RUN)/wiki.py query $(QUERY_FLAGS) --question "$(QUESTION)" $(LLM_EXTRA)

audit:
	$(RUN)/wiki.py audit $(AUDIT_FLAGS) $(LLM_EXTRA)

analyze:
	@test -n "$(TICKER)" || (echo "Usage: make analyze TICKER=MSFT"; exit 1)
	$(RUN)/analyze.py "$(TICKER)"

rebuild-indexes:
	$(RUN)/wiki.py rebuild-indexes --wiki "$(WIKI)"

backfill-sources:
	$(RUN)/wiki.py backfill-sources $(SYNC_FLAGS)

backfill-titles:
	$(RUN)/wiki.py backfill-titles $(SYNC_FLAGS)

publish:
	DEPLOY="$(DEPLOY)" DRY_RUN="$(DRY_RUN)" LLM_PROVIDER="$(LLM_PROVIDER)" scripts/publish.sh

site-prepare: venv
	$(RUN)/wiki.py site-prepare --wiki "$(WIKI)" --content "$(SITE_CONTENT)"

site-install:
	cd "$(SITE_DIR)" && npm install

site-build: site-prepare
	cd "$(SITE_DIR)" && npm run quartz -- build --output "$(abspath $(SITE_OUTPUT))"

site-serve: site-prepare
	cd "$(SITE_DIR)" && npm run quartz -- build --serve --port "$(SITE_PORT)" --output "$(abspath $(SITE_OUTPUT))"

site-deploy: site-build
	npx wrangler pages deploy "$(SITE_OUTPUT)" --project-name "$(PAGES_PROJECT)" --branch "$(PAGES_BRANCH)" --commit-dirty=true
	@echo "Production site: $(PAGES_URL)"

site:
ifeq ($(SERVE),1)
	@$(MAKE) site-serve
else ifeq ($(DEPLOY),1)
	@$(MAKE) site-deploy
else
	@$(MAKE) site-build
endif

launchd:
ifeq ($(ACTION),unload)
	launchctl bootout "gui/$$(id -u)/com.zhaowenlong.dev-business.publish"
	@echo "Unloaded com.zhaowenlong.dev-business.publish"
else ifeq ($(ACTION),test)
	launchctl kickstart -kp "gui/$$(id -u)/com.zhaowenlong.dev-business.publish"
else
	@mkdir -p logs
	cp launchd/com.zhaowenlong.dev-business.publish.plist ~/Library/LaunchAgents/
	-launchctl bootout "gui/$$(id -u)/com.zhaowenlong.dev-business.publish" 2>/dev/null || true
	launchctl bootstrap "gui/$$(id -u)" ~/Library/LaunchAgents/com.zhaowenlong.dev-business.publish.plist
	@echo "Installed com.zhaowenlong.dev-business.publish (Sunday 24:00 / Mon 00:00)"
endif
