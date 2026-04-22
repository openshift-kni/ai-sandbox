.PHONY: setup eval eval-view lint clean help

# Ensure promptfoo uses the uv-managed Python (has pyyaml etc.)
export PROMPTFOO_PYTHON := $(shell cd .. && uv run which python)

setup: ## Install eval dependencies
	npm install -g promptfoo
	npm install @anthropic-ai/claude-agent-sdk
	cd .. && uv sync

eval: ## Run all evals
	promptfoo eval --no-cache

eval-view: ## View eval results in browser
	promptfoo view

lint: ## Lint Python assertion files
	cd .. && uv run ruff check evals/assertions/

clean: ## Clear eval cache
	promptfoo cache clear

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
