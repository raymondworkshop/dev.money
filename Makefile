# dev.business — wiki sync, site, automation

PYTHON = $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHONPATH := $(CURDIR)/scripts
export PYTHONPATH
RUN = $(PYTHON) scripts

# Paths
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

# Flags
LLM_PROVIDER ?= local-gateway
DRY_RUN ?=
ALL ?=
REVIEW ?=
NO_ARCHIVE ?=
FILE ?=
QUESTION ?=
TICKER ?=
DEPLOY ?=
SERVE ?=
PREPARE ?= 1
FORCE_PREPARE ?=
ACTION ?= install
DENSIFY ?= 1
BACKFILL_COMPANIES ?= 1

WIKI_FLAGS = --source "$(SOURCE)" --wiki "$(WIKI)"
SYNC_FLAGS = $(WIKI_FLAGS) --archive "$(ARCHIVE)" \
	$(if $(DRY_RUN),--dry-run) $(if $(ALL),--all) $(if $(REVIEW),--include-review) \
	$(if $(NO_ARCHIVE),--no-archive) $(if $(FILE),--file "$(FILE)") \
	--provider "$(LLM_PROVIDER)"
LLM_FLAGS = $(if $(DRY_RUN),--dry-run) --provider "$(LLM_PROVIDER)"
DENSIFY_FLAGS = --wiki "$(WIKI)" $(if $(DRY_RUN),--dry-run)
QUARTZ_OUT = --output "$(abspath $(SITE_OUTPUT))"

.DEFAULT_GOAL := help
.PHONY: help test venv sync densify densify-links query audit analyze publish \
	site site-prepare site-install site-build site-serve site-deploy \
	rebuild-indexes repair-index-labels backfill-companies backfill-sources \
	backfill-titles launchd

help:
	@echo "dev.business"
	@echo ""
	@echo "  make sync                              raw → wiki → densify → 关键公司"
	@echo "  make sync LLM_PROVIDER=gemini DRY_RUN=1"
	@echo "  make query QUESTION=\"What is Nvidia's moat?\""
	@echo "  make audit"
	@echo "  make analyze TICKER=MSFT"
	@echo "  make site                              build Quartz"
	@echo "  make site SERVE=1 SITE_PORT=8081       local preview"
	@echo "  make site DEPLOY=1                     build + Cloudflare Pages"
	@echo "  make publish                           sync + deploy (DEPLOY=0 sync only)"
	@echo "  make test | make venv | make launchd"
	@echo ""
	@echo "  Sync opts:  ALL=1  REVIEW=1  FILE=name.md  NO_ARCHIVE=1"
	@echo "              DENSIFY=0  BACKFILL_COMPANIES=0"
	@echo "  Site opts:  PREPARE=0  FORCE_PREPARE=1"
	@echo "  Maint:      densify  rebuild-indexes  backfill-companies"
	@echo "              backfill-sources  backfill-titles  repair-index-labels"

test: ; $(RUN)/test_suite.py

venv:
	@test -x .venv/bin/python || python3 -m venv .venv
	@if [ ! -f .venv/.reqs-stamp ] || [ requirements.txt -nt .venv/.reqs-stamp ]; then \
		.venv/bin/pip install -r requirements.txt && touch .venv/.reqs-stamp; \
	fi

# raw → wiki → densify → fill empty 关键公司
sync:
	@mkdir -p logs
	@echo "=== sync $$(date -Iseconds) LLM_PROVIDER=$(LLM_PROVIDER) ===" | tee -a logs/sync.log
	@$(RUN)/wiki.py sync $(SYNC_FLAGS) 2>&1 | tee -a logs/sync.log; status=$${PIPESTATUS[0]}; \
	if [ $$status -eq 0 ] && [ "$(DENSIFY)" != "0" ]; then \
		echo "=== densify $$(date -Iseconds) ===" | tee -a logs/sync.log; \
		$(RUN)/wiki.py densify-links $(DENSIFY_FLAGS) 2>&1 | tee -a logs/sync.log; status=$${PIPESTATUS[0]}; \
	fi; \
	if [ $$status -eq 0 ] && [ "$(BACKFILL_COMPANIES)" != "0" ]; then \
		echo "=== backfill-companies $$(date -Iseconds) ===" | tee -a logs/sync.log; \
		$(RUN)/wiki.py rebuild-indexes --wiki "$(WIKI)" --backfill-companies 2>&1 | tee -a logs/sync.log; status=$${PIPESTATUS[0]}; \
	fi; \
	exit $$status

densify densify-links: ; $(RUN)/wiki.py densify-links $(DENSIFY_FLAGS)

query:
	@test -n "$(QUESTION)" || (echo 'Usage: make query QUESTION="..."'; exit 1)
	$(RUN)/wiki.py query $(WIKI_FLAGS) --outputs "$(OUTPUTS)" --question "$(QUESTION)" $(LLM_FLAGS)

audit: ; $(RUN)/wiki.py audit $(WIKI_FLAGS) --outputs "$(OUTPUTS)" $(LLM_FLAGS)

analyze:
	@test -n "$(TICKER)" || (echo "Usage: make analyze TICKER=MSFT"; exit 1)
	$(RUN)/analyze.py "$(TICKER)"

rebuild-indexes: ; $(RUN)/wiki.py rebuild-indexes --wiki "$(WIKI)"
repair-index-labels: ; $(RUN)/wiki.py rebuild-indexes --wiki "$(WIKI)" --repair-index-labels
backfill-companies: ; $(RUN)/wiki.py rebuild-indexes --wiki "$(WIKI)" --backfill-companies
backfill-sources: ; $(RUN)/wiki.py backfill-sources $(WIKI_FLAGS) --archive "$(ARCHIVE)"
backfill-titles: ; $(RUN)/wiki.py backfill-titles $(WIKI_FLAGS) --archive "$(ARCHIVE)"

publish:
	DEPLOY="$(DEPLOY)" DRY_RUN="$(DRY_RUN)" LLM_PROVIDER="$(LLM_PROVIDER)" scripts/publish.sh

site-prepare: venv
	$(RUN)/wiki.py site-prepare --wiki "$(WIKI)" --content "$(SITE_CONTENT)" \
		$(if $(FORCE_PREPARE),--force)

site-install: ; cd "$(SITE_DIR)" && npm install

site-build: site-prepare
	cd "$(SITE_DIR)" && npm run quartz -- build $(QUARTZ_OUT)

site-serve:
ifeq ($(PREPARE),0)
	@test -f "$(SITE_CONTENT)/index.md" || (echo "Missing $(SITE_CONTENT); run without PREPARE=0 first" && exit 1)
else
	@$(MAKE) site-prepare
endif
	cd "$(SITE_DIR)" && npm run quartz -- build --serve --port "$(SITE_PORT)" $(QUARTZ_OUT)

site-deploy: site-build
	npx wrangler pages deploy "$(SITE_OUTPUT)" --project-name "$(PAGES_PROJECT)" \
		--branch "$(PAGES_BRANCH)" --commit-dirty=true
	@echo "Production site: $(PAGES_URL)"

site:
ifeq ($(SERVE),1)
	@$(MAKE) site-serve
else ifeq ($(DEPLOY),1)
	@$(MAKE) site-deploy
else
	@$(MAKE) site-build
endif

# ACTION=install|unload|test
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
	@echo "Installed com.zhaowenlong.dev-business.publish (Mon 00:00, Wed 00:00)"
endif
