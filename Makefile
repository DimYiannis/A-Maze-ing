CONFIG = config.txt
AMAZING = a_maze_ing.py
PYTHON = python3
SRC_DIR = .

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) $(AMAZING) $(CONFIG)

debug:
	$(PYTHON) -m pdb $(PYTHON) $(AMAZING) $(CONFIG)

lint:
	flake8 $(SRC_DIR)
	mypy $(SRC_DIR) \
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

lint_strict:
	flake8 $(SRC_DIR)
	mypy $(SRC_DIR) --strict

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "clean done"


.PHONY: install run debug lint lint_strict test clean

