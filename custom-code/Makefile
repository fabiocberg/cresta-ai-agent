.PHONY: install test lint serve

# Use uv if available, fall back to pip.
UV := $(shell command -v uv 2>/dev/null)
ifdef UV
  PIP_INSTALL = uv pip install
else
  PIP_INSTALL = pip install
endif

# Dependencies are declared in pyproject.toml (the single source of truth).
install:
	$(PIP_INSTALL) -e ".[test]"

test:
	PYTHONPATH=. pytest tests/

lint:
	$(PIP_INSTALL) ruff
	ruff check .

serve:
	cresta custom-code serve .
