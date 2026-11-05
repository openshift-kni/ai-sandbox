.PHONY: setup preflight eval eval-repeat eval-view lint clean \
	preflight-openshell eval-openshell eval-openshell-recorded package-openshell-results \
	openshell-view help

REPO_ROOT := $(abspath ../..)
PROMPTFOO_PYTHON ?= $(REPO_ROOT)/.venv/bin/python
export PROMPTFOO_PYTHON

PROMPTFOO_EVAL_ARGS ?=
PROMPTFOO_CONCURRENCY ?= 3
SANDBOX_RESULTS_DIR ?= /sandbox/rds-eval-results
OPENSHELL_RESULTS_DIR ?= $(CURDIR)/results/$(if $(strip $(OPENSHELL_SANDBOX)),$(OPENSHELL_SANDBOX),latest)

setup: ## Install pinned eval dependencies (promptfoo + claude-agent-sdk)
	npm ci
	cd ../.. && uv sync

preflight: ## Verify the gateway URL, key and models are set before an eval run
	@missing=""; \
	for var in ANTHROPIC_BASE_URL ANTHROPIC_API_KEY RDS_AGENT_MODEL RDS_GRADER_MODEL; do \
	  [ -n "$$(printenv $$var)" ] || missing="$$missing $$var"; \
	done; \
	if [ -n "$$missing" ]; then \
	  echo "preflight: unset var(s):$$missing" >&2; \
	  exit 1; \
	fi

# The agent has unrestricted bash and the eval needs no cluster, so KUBECONFIG
# is emptied.
eval: preflight ## Run all evals (single pass)
	KUBECONFIG=/dev/null npx promptfoo eval --no-cache $(PROMPTFOO_EVAL_ARGS)

eval-repeat: preflight ## Run all evals 3x to measure variance
	KUBECONFIG=/dev/null npx promptfoo eval --no-cache --repeat 3 $(PROMPTFOO_EVAL_ARGS)

eval-view: ## View eval results in browser
	npx promptfoo view

lint: ## Lint Python assertion files and the OpenShell scripts
	cd ../.. && uv run ruff check rds-policy/evals/assertions/
	shellcheck scripts/*.sh

clean: ## Clear eval cache
	npx promptfoo cache clear

# ---- Targets below run inside the sandbox (started by `scripts/run.sh`) ----

# The attached provider injects a placeholder in GOOGLE_VERTEX_AI_TOKEN and the
# sandbox proxy swaps in the real short-lived credential on requests to Vertex.
# Claude Code sends it as its bearer token (Google auth skipped via
# CLAUDE_CODE_SKIP_VERTEX_AUTH, set at create); the judge's HTTP client in
# openshell-grader.yaml does the same.
# Drop PROMPTFOO_CONCURRENCY to 1 if a run reports policy_denied with
# "ambiguous shared socket ownership" (seen once, on the old ADC refresh path).
eval-openshell: preflight-openshell
	mkdir -p "$(SANDBOX_RESULTS_DIR)"
	ANTHROPIC_AUTH_TOKEN="$$GOOGLE_VERTEX_AI_TOKEN" PROMPTFOO_DISABLE_TELEMETRY=1 \
		npx promptfoo eval --no-cache --max-concurrency $(PROMPTFOO_CONCURRENCY) --grader file://openshell-grader.yaml --output "$(SANDBOX_RESULTS_DIR)/promptfoo.json" $(PROMPTFOO_EVAL_ARGS)

preflight-openshell:
	@missing=""; \
	[ -n "$$ANTHROPIC_VERTEX_PROJECT_ID" ] || missing="$$missing ANTHROPIC_VERTEX_PROJECT_ID"; \
	[ -n "$$CLOUD_ML_REGION" ] || missing="$$missing CLOUD_ML_REGION"; \
	if [ -n "$$missing" ]; then \
	  echo "preflight: unset Vertex var(s):$$missing" >&2; \
	  echo "  Agent (Opus 4.8) and the Sonnet 5 grader both go direct to Vertex; set project + region (e.g. CLOUD_ML_REGION=global) or the grader config interpolates to empty." >&2; \
	  exit 1; \
	fi; \
	adc="$${GOOGLE_APPLICATION_CREDENTIALS:-$$HOME/.config/gcloud/application_default_credentials.json}"; \
	if [ -z "$$GOOGLE_VERTEX_AI_TOKEN" ] && [ ! -f "$$adc" ]; then \
	  echo "preflight: warning — no ADC at $$adc (run 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS)." >&2; \
	fi; \
	echo "preflight: Vertex project/region set; the grading project needs claude-sonnet-5 access + Anthropic data sharing, or Vertex returns 403."

# Detached job: install, run, record the exit code for run.sh to poll.
eval-openshell-recorded:
	@mkdir -p "$(SANDBOX_RESULTS_DIR)"; \
	{ $(MAKE) setup && $(MAKE) eval-openshell; } >"$(SANDBOX_RESULTS_DIR)/eval.log" 2>&1; \
	printf '%s\n' "$$?" >"$(SANDBOX_RESULTS_DIR)/exit-code"

package-openshell-results:
	@mkdir -p "$(SANDBOX_RESULTS_DIR)"
	@[ ! -d "$$HOME/.promptfoo" ] || cp -R "$$HOME/.promptfoo" "$(SANDBOX_RESULTS_DIR)/promptfoo-state"
	@for path in /tmp/rds-merge-*; do [ ! -e "$$path" ] || cp -R "$$path" "$(SANDBOX_RESULTS_DIR)/"; done

# ---- Host-side steps: one small script each in scripts/ ----

# `make openshell-run` runs `scripts/run.sh`, and so on. The scripts also run
# directly; settings given to make are passed through to them. Each script's
# header lists the variables it reads.
openshell-%:
	@scripts/$*.sh

openshell-view: ## View downloaded results with the preserved Promptfoo database
	@test -f "$(OPENSHELL_RESULTS_DIR)/promptfoo-state/promptfoo.db" || { echo "no downloaded Promptfoo database in $(OPENSHELL_RESULTS_DIR)" >&2; exit 1; }
	PROMPTFOO_CONFIG_DIR="$(OPENSHELL_RESULTS_DIR)/promptfoo-state" npx promptfoo view

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\033[36m%-28s\033[0m %s\n' 'openshell-<script>' 'Run scripts/<script>.sh: setup (once), run, collect, clean'
