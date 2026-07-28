PY := ./.venv/bin/python
SC := scenarios

.PHONY: setup test validate gate gate6 smoke run metrics web dev-api dev-ui clean

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

## The same gate on market 6, the equidistant control, and on the seed the control arm
## actually runs. Separate from `gate` rather than folded into it: market 6 is not one of
## the paper's, so a red `gate` must keep meaning "the replication is broken".
gate6:
	@for k in re pi zi; do \
		echo "=== market 6, scripted $$k ==="; \
		$(PY) -m ps1982 run --scenario $(SC)/m6_scripted_$$k.yaml 2>&1 | tail -20; \
	done

smoke:
	$(PY) -m ps1982 run --scenario $(SC)/smoke.yaml

run:
	$(PY) -m ps1982 run --scenario $(SC)/market3_paper_exact.yaml

## Rescore the most recent log. `find` rather than a glob: runs are grouped one level
## deeper now (runs/<group>/<run>/<stamp>.jsonl) and a fixed-depth glob silently matched
## nothing after that change.
metrics:
	@f=$$(find runs -name '*.jsonl' -type f -print0 | xargs -0 ls -t | head -1); \
	 echo "$$f"; $(PY) -m ps1982 metrics --run "$$f"

web:
	cd web && npm run start

dev-api:
	cd web && npm run dev:api

dev-ui:
	cd web && npm run dev

clean:
	rm -rf .pytest_cache web/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
