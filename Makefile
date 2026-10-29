.PHONY: help setup setup-pip test lint app clean

help:  ## List targets
	@grep -E "^[a-z-]+:.*##" $(MAKEFILE_LIST) | sed "s/:.*##/:/"

setup:  ## Create .venv and install with uv (runtime + dev deps)
	uv sync --extra dev

setup-pip:  ## Alternative without uv (inside an activated virtualenv)
	pip install -e ".[dev]"

test:  ## Run the offline test suite
	uv run --extra dev pytest

lint:  ## Ruff lint
	uv run --extra dev ruff check .

app:  ## Launch the Streamlit app
	uv run streamlit run app.py

clean:  ## Remove caches
	rm -rf .pytest_cache .ruff_cache **/__pycache__
