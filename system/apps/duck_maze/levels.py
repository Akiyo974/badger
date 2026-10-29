"""Duck Maze levels: 16 x 11 cells of 20 px under a 20 px status bar.

# wall   . floor   S start   D duck to collect   O bug hole   E exit
The exit opens once every duck is collected. tests/test_duck_maze.py checks
that each level is the right size and can be finished without crossing a hole.
"""

COLS = 16
ROWS = 11

LEVELS = (
    ("hello, world", (
        "################",
        "#S.............#",
        "#..............#",
        "#...######.....#",
        "#........#.....#",
        "#..D.....#.....#",
        "#........#.....#",
        "#...######.....#",
        "#..............#",
        "#.............E#",
        "################",
    )),
    ("first commit", (
        "################",
        "#S...#.........#",
        "#....#..D......#",
        "#....#....####.#",
        "#....####.#....#",
        "#.........#....#",
        "#.######..#..###",
        "#.#....#..#....#",
        "#.#.D..#.......#",
        "#......#......E#",
        "################",
    )),
    ("bug hunt", (
        "################",
        "#S.....O.......#",
        "#..........O...#",
        "#.####.####....#",
        "#.#..D....#..O.#",
        "#.#..O....#....#",
        "#.#.......####.#",
        "#.####.O.......#",
        "#......#..D..O.#",
        "#..O...#......E#",
        "################",
    )),
    ("merge conflict", (
        "################",
        "#S.#.....#....D#",
        "#.O#.##..#.##..#",
        "#..#..#O.#..#..#",
        "#.....#.....#..#",
        "####..####..#O.#",
        "#D.#....O#.....#",
        "#..#..O..#.##..#",
        "#..####..#..#O.#",
        "#.........O.#.E#",
        "################",
    )),
    ("hotfix", (
        "################",
        "#S.....#..D....#",
        "#.###..#..##.O.#",
        "#...#..O.......#",
        "###.#..###.###.#",
        "#D..#....#...#.#",
        "#.O.####.#.O.#.#",
        "#........#...#.#",
        "#.##O.##.###O#.#",
        "#......O......E#",
        "################",
    )),
    ("ship it", (
        "################",
        "#S.O...#...O..D#",
        "#.##.#.#.#.##..#",
        "#..#.#...#..#O.#",
        "##.#.#####.O#..#",
        "#..#...O.....#.#",
        "#.O###.##.O#.#.#",
        "#...D#..#..#...#",
        "#.O..#O.#.D#.O.#",
        "#..O......O#..E#",
        "################",
    )),
)


def parse(rows):
    """Cell sets and positions of one level, as (column, row) pairs."""
    walls, holes, ducks = set(), set(), []
    start = exit_cell = None
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == "#":
                walls.add((x, y))
            elif cell == "O":
                holes.add((x, y))
            elif cell == "D":
                ducks.append((x, y))
            elif cell == "S":
                start = (x, y)
            elif cell == "E":
                exit_cell = (x, y)
    return walls, holes, ducks, start, exit_cell
