.PHONY: init test-ci lint setup setup-rh-pre-commit install-uv

install-uv:
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }

init: install-uv setup-rh-pre-commit

test-ci: install-uv lint

lint:
	uv run ruff check .
	uv run ruff format --check .

setup:
	uv run pre-commit install

# VPN required for auth token login to RH internal pattern server
setup-rh-pre-commit: setup
	@echo "Installing rh-pre-commit hooks (requires VPN)..."
	uv run pre-commit run rh-pre-commit --all-files || true
	@echo "Installing rh-gitleaks into project venv..."
	uv pip install "rh-gitleaks @ git+https://gitlab.cee.redhat.com/infosec-public/developer-workbench/tools.git#subdirectory=rh-gitleaks"
	@echo "Logging in to rh-gitleaks pattern server..."
	uv run python3 -m rh_gitleaks login
