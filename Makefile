.PHONY: install verify test lint typecheck clean

install:
	pip install -e ".[dev]"

verify: lint typecheck test
	@echo ""
	@echo "verify ok — package imports, lint clean, types check, tests pass."

test:
	pytest -q

lint:
	ruff check india_energy_atlas tests
	ruff format --check india_energy_atlas tests

typecheck:
	mypy india_energy_atlas

clean:
	rm -rf .pytest_cache __pycache__ india_energy_atlas/__pycache__ tests/__pycache__
	rm -rf .ruff_cache .mypy_cache
	rm -rf build dist *.egg-info
