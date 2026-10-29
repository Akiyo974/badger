"""Checks the Duck Maze levels: size, one start and one exit, and that every
duck and the exit can be reached without crossing a bug hole.

Run from the repo root: py tests/test_duck_maze.py
"""
import os
import sys
import unittest
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system", "apps", "duck_maze"))

import levels  # noqa: E402


def reachable(walls, holes, start):
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (x + step[0], y + step[1])
            if cell not in seen and cell not in walls and cell not in holes:
                seen.add(cell)
                queue.append(cell)
    return seen


class LevelsTest(unittest.TestCase):
    def test_sizes_and_markers(self):
        self.assertGreaterEqual(len(levels.LEVELS), 6)
        for name, rows in levels.LEVELS:
            with self.subTest(level=name):
                self.assertEqual(len(rows), levels.ROWS)
                for row in rows:
                    self.assertEqual(len(row), levels.COLS, row)
                    self.assertTrue(set(row) <= set("#.SDOE"), row)
                text = "".join(rows)
                self.assertEqual(text.count("S"), 1)
                self.assertEqual(text.count("E"), 1)
                self.assertGreaterEqual(text.count("D"), 1)

    def test_closed_border(self):
        for name, rows in levels.LEVELS:
            with self.subTest(level=name):
                self.assertEqual(set(rows[0]), {"#"})
                self.assertEqual(set(rows[-1]), {"#"})
                for row in rows:
                    self.assertEqual((row[0], row[-1]), ("#", "#"))

    def test_finishable_without_holes(self):
        for name, rows in levels.LEVELS:
            with self.subTest(level=name):
                walls, holes, ducks, start, exit_cell = levels.parse(rows)
                seen = reachable(walls, holes, start)
                for duck in ducks:
                    self.assertIn(duck, seen, "duck %s unreachable" % (duck,))
                self.assertIn(exit_cell, seen)

    def test_difficulty_grows(self):
        holes = [len(levels.parse(rows)[1]) for _, rows in levels.LEVELS]
        self.assertEqual(holes[0], 0)
        self.assertEqual(holes, sorted(holes))


if __name__ == "__main__":
    unittest.main(verbosity=1)
