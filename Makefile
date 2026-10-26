.PHONY: run test demo-errors

CONFIG ?= examples/config_remote.csv
export PYTHONDONTWRITEBYTECODE = 1
export PYTHONPATH = src

run:
	python3 -m depgraph --config $(CONFIG)

test:
	python3 -m unittest discover -s tests -v

demo-errors:
	@for file in examples/errors/*.csv; do \
		echo "=== $$file"; \
		python3 -m depgraph --config $$file; \
	done; true
