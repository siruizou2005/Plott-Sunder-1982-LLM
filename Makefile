PY := ./.venv/bin/python
SC := scenarios

.PHONY: setup test validate gate smoke run metrics web dev-api dev-ui clean

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q -e ".[dev]"
	cd web && npm install

test:
	$(PY) -m pytest

validate:
	$(PY) -m ps1982 validate --scenario $(SC)/market3_paper_exact.yaml

## The engine correctness gate: each scripted agent must produce its own model's outcome.
## Zero API cost. Run this before spending anything on model calls.
gate:
	@for k in re pi zi; do \
		echo "=== scripted $$k ==="; \
		$(PY) -m ps1982 run --scenario $(SC)/market3_scripted_$$k.yaml 2>&1 | tail -20; \
	done

smoke:
	$(PY) -m ps1982 run --scenario $(SC)/smoke.yaml

run:
	$(PY) -m ps1982 run --scenario $(SC)/market3_paper_exact.yaml

metrics:
	@f=$$(ls -t runs/*/*.jsonl | head -1); echo "$$f"; $(PY) -m ps1982 metrics --run "$$f"

web:
	cd web && npm run start

dev-api:
	cd web && npm run dev:api

dev-ui:
	cd web && npm run dev

clean:
	rm -rf .pytest_cache web/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
