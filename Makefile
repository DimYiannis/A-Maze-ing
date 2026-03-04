MAZE = maze.txt
AMAZING = a_maze_ing.py
PYTHON = python3

display:
	$(PYTHON) $(AMAZING) $(MAZE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "clean done"


.PHONY: install run debug lint lint_strict test clean display

