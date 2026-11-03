PYTHON ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup test run seed serve clean lint fmt

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements.txt

test:
	$(BIN)/pytest

seed:
	$(BIN)/flask --app taskboard seed

run:
	$(BIN)/flask --app taskboard run --debug --port 5050

serve:
	$(BIN)/gunicorn "taskboard:create_app()"

lint:
	$(BIN)/ruff check . && $(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff check --fix --exit-zero . && $(BIN)/ruff format . && $(BIN)/ruff check .

clean:
	rm -rf $(VENV) instance .pytest_cache
