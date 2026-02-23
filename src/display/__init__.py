"""
display
=======
Graphical maze display for A-Maze-ing.

Usage::

    from display import MazeDisplay
    MazeDisplay("maze.txt").run()
"""

from .window import MazeDisplay

__all__ = ["MazeDisplay"]
