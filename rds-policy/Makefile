.PHONY: build help

IMAGE ?= rds-policy-skill:latest

build: ## Build the content-only skill image (podman)
	podman build -f Containerfile --ignorefile .containerignore -t $(IMAGE) ../agentic-plugins/rh-telco

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
