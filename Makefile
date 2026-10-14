PYTHON ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup test run seed clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements.txt

test:
	$(BIN)/pytest

seed:
	$(BIN)/flask --app taskboard seed

run:
	$(BIN)/flask --app taskboard run --debug --port 5050

clean:
	rm -rf $(VENV) instance .pytest_cache
