PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: help venv install-dev health smoke test clean

help:
	@echo "Targets:"
	@echo "  make venv         Create local virtualenv"
	@echo "  make install-dev  Install test/dev dependencies"
	@echo "  make health       Run local health checks"
	@echo "  make smoke        Run deterministic fake pipeline smoke"
	@echo "  make test         Run pytest suite"
	@echo "  make clean        Remove test caches"

venv:
	$(PYTHON) -m venv $(VENV)

install-dev: venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -r requirements-dev.txt

health:
	$(PYTHON) scripts/healthcheck.py

smoke:
	$(PYTHON) scripts/smoke_fake_pipeline.py

test:
	$(PYTHON) -m pytest

clean:
	rm -rf .pytest_cache tests/.pytest_cache scripts/__pycache__ tests/__pycache__
