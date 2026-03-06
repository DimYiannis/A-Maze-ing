CONFIG = config.txt
AMAZING = a_maze_ing.py
PYTHON = python3
SRC_DIR = .

install:
	$(PYTHON) -m pip install -r requirements.txt

build:
	uv build --out-dir .

run:
	$(PYTHON) $(AMAZING) $(CONFIG)

debug:
	$(PYTHON) -m pdb $(AMAZING) $(CONFIG)

lint:
	flake8 $(SRC_DIR) --exclude .venv
	mypy $(SRC_DIR) \
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

lint-strict:
	flake8 $(SRC_DIR)  --exclude .venv
	mypy $(SRC_DIR) --strict

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name mazegen.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "clean done"


.PHONY: install run debug lint lint-strict test clean build

