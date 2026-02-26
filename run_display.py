"""Launcher — run from the project root: python3 run_display.py maze.txt"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from display.window import main

main()

