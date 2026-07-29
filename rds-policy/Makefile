.PHONY: build help

IMAGE ?= rds-policy-skill:latest

build: ## Build the content-only skill image (podman)
	podman build -f Containerfile -t $(IMAGE) .

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
