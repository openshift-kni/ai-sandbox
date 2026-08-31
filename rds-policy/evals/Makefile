.PHONY: setup preflight eval eval-repeat eval-view lint clean help

# Ensure promptfoo uses the uv-managed Python (has pyyaml etc.)
export PROMPTFOO_PYTHON := $(shell cd .. && uv run which python)

setup: ## Install pinned eval dependencies (promptfoo + claude-agent-sdk)
	npm ci
	cd .. && uv sync

preflight: ## Verify Vertex prerequisites before an eval run
	@missing=""; \
	[ -n "$$ANTHROPIC_VERTEX_PROJECT_ID" ] || missing="$$missing ANTHROPIC_VERTEX_PROJECT_ID"; \
	[ -n "$$CLOUD_ML_REGION" ] || missing="$$missing CLOUD_ML_REGION"; \
	if [ -n "$$missing" ]; then \
	  echo "preflight: unset Vertex var(s):$$missing" >&2; \
	  echo "  Agent (Opus 4.8) and the default Sonnet 5 grader both go direct to Vertex; set project + region (e.g. CLOUD_ML_REGION=global) or the grader config interpolates to empty." >&2; \
	  exit 1; \
	fi; \
	adc="$${GOOGLE_APPLICATION_CREDENTIALS:-$$HOME/.config/gcloud/application_default_credentials.json}"; \
	[ -f "$$adc" ] || echo "preflight: warning — no ADC at $$adc (run 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS)." >&2; \
	echo "preflight: Vertex project/region set; the grading project needs claude-sonnet-5 access + Anthropic data sharing, or Vertex returns 403."

eval: preflight ## Run all evals (single pass)
	npx promptfoo eval --no-cache

eval-repeat: preflight ## Run all evals 3x to measure variance
	npx promptfoo eval --no-cache --repeat 3

eval-view: ## View eval results in browser
	npx promptfoo view

lint: ## Lint Python assertion files
	cd .. && uv run ruff check evals/assertions/

clean: ## Clear eval cache
	npx promptfoo cache clear

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
