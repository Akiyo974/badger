# Duck Maze

Tilt the badge to roll a marble through six mazes drawn like a contribution graph. Collect every rubber duck to open the merge, then roll into it. Avoid the bug holes.

![Duck Maze title screen](../screenshots/duck-maze-title.png)

## Before you start

Install it from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)). It needs no settings and no network.

## How to play

1. On the title screen, choose a level with **← / →**.
2. Hold the badge the way you want to play (flat, or tilted towards you), then press **Select**. That position counts as level.
3. Tilt to roll the marble. Pick up every 🦆: the merge opens once they are all collected.
4. Roll into the merge to finish. A bug hole sends you back to the start of the level.
5. **Back** returns to the title screen.

![Level 3, bug hunt](../screenshots/duck-maze.png)

## Levels

Six levels, from no holes to twelve: *hello, world*, *first commit*, *bug hunt*, *merge conflict*, *hotfix*, *ship it*. Finishing a level unlocks the next. Unlocked levels and your best times are kept across restarts.

## Tips

- Small tilts: the marble accelerates towards the side you lean to, and bounces off the walls.
- If the marble drifts on its own, go back to the title and press **Select** again while holding the badge still.

## Make your own levels

Levels are text grids in [`levels.py`](https://github.com/Akiyo974/badger/blob/main/system/apps/duck_maze/levels.py). `py tests/test_duck_maze.py` checks that every duck and the merge can be reached without crossing a hole.

Source: [`system/apps/duck_maze`](https://github.com/Akiyo974/badger/tree/main/system/apps/duck_maze)
