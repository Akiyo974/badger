"""
Look after Mona. Play with her, feed her and clean up after her.

Controls:
* < = Play a matching game with her
* > = Pick something to feed her
* Enter = Clean up after her
* Up = Run her day faster
* Down = Show her walk: steps from the watch, what she needs, her mood
* Upside down: left and right pick a button, Enter presses it
* In the matching game, hold Enter to stop playing
"""

badge.mode(LORES | VSYNC)

import clock
import food
import icons
import match
import tufty
import ui
import walk
from badgeware import State

# how much faster the day runs with UP held
WARP = 100

# how long each need takes to empty, in Tufty's own hours, so they keep their
# pace against his day however fast it is set to run
HAPPY_HOURS = 12
HUNGER_HOURS = 8
CLEAN_HOURS = 16

BUTTONS = ("play", "feed", "clean")
MOVES = ((BUTTON_LEFT, -1, 0), (BUTTON_RIGHT, 1, 0), (BUTTON_UP, 0, -1), (BUTTON_DOWN, 0, 1))
GAME_SPOT = 132
MATCH_HAPPY = 10
CLEARED_HAPPY = 30
QUIT_HOLD_MS = 1000
SAD_FACE = ")"
SAD_FILL = color.rgb(249, 193, 62)
# where she waits beside the walk panel
WALK_SPOT = 26
WALK_CHECK_S = 5

stats_shown = False
cursor = 0
game = None
picker = None
select_down_at = None


def draw(hour, minute):
  ui.background(clock.look(hour, minute))
  pet.draw()

  # the buttons, on a strip wiped clear of whatever was there last frame
  screen.pen = color.rgb(0, 0, 0)
  screen.rectangle(0, 106, 160, 14)

  if pet.asleep():
    # nothing rouses her early, so there is nothing to press
    ui.draw_strip_text("Mona is sleeping. Zzz.")
  elif stats_shown:
    ui.draw_strip_text(steps.strip_text())
  elif game is not None:
    ui.draw_strip_text("FIND THE PAIRS: %d LEFT" % game.pairs_left())
  elif picker is not None:
    ui.draw_strip_text(picker.caption())
  elif pet.alive():
    choosing = badge.rotate_180()
    for index, (x, label, action) in enumerate(((7, "play", "dance"), (57, "feed", "eat"), (107, "clean", "clean"))):
      lit = index == cursor if choosing else pet.current_action() == action
      ui.draw_button(x, 106, label, lit)
  else:
    ui.draw_button(107, 106, "reset", False)

  if game is not None:
    game.draw()
    if game.sad():
      x, y = pet.position()
      icons.draw("emoji", SAD_FACE, x - icons.WIDTH // 2, y - 66, SAD_FILL)
  elif picker is not None:
    picker.draw()

  ui.draw_glitch(min(pet.hunger(), pet.clean(), pet.happy()))
  ui.draw_scanlines(ui.SCENE)

  # the readouts go on after the filter, so the scanlines do not cross them
  if game is None:
    ui.draw_clock(hour, minute)
  if stats_shown:
    steps.draw(pet)

  ui.draw_header()


def titles():
  """Hold on the title screen until Enter lets her out."""
  while True:
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    ui.draw_intro(tufty.frame("dance"))
    ui.draw_scanlines()
    ui.draw_header()
    badge.update()

    if badge.pressed(BUTTON_SELECT):
      # use the press up here, or the game's first frame sees it too and
      # cleans her
      badge.update()
      return


def activate(button):
  global game, picker, stats_shown
  if button in ("play", "feed"):
    stats_shown = False
  if button == "play":
    game = match.Match()
    pet.do_action(None)
    pet.set_mood("idle")
    pet.place(GAME_SPOT)
  elif button == "feed":
    picker = food.Picker()
  else:
    pet.clean(30)
    pet.do_action("clean")


def choose_button():
  global cursor
  if badge.rotate_180():
    if badge.pressed(BUTTON_LEFT):
      cursor = max(0, cursor - 1)
    if badge.pressed(BUTTON_RIGHT):
      cursor = min(len(BUTTONS) - 1, cursor + 1)
    if badge.pressed(BUTTON_SELECT):
      activate(BUTTONS[cursor])
    return
  if badge.pressed(BUTTON_LEFT):
    activate("play")
  if badge.pressed(BUTTON_RIGHT):
    activate("feed")
  if badge.pressed(BUTTON_SELECT):
    activate("clean")


def play_game():
  global game, select_down_at
  if badge.pressed(BUTTON_SELECT):
    select_down_at = badge.ticks
  elif not badge.held(BUTTON_SELECT):
    select_down_at = None
  holding = select_down_at is not None and badge.ticks - select_down_at >= QUIT_HOLD_MS
  if badge.pressed(BUTTON_BACK) or holding:
    game = None
    select_down_at = None
    return
  for button, dx, dy in MOVES:
    if badge.pressed(button):
      game.move(dx, dy)
  if badge.pressed(BUTTON_SELECT):
    result = game.select()
    if result in ("match", "cleared"):
      pet.happy(MATCH_HAPPY)
      pet.do_action("heart")
  game.update()
  if game.finished():
    pet.happy(CLEARED_HAPPY)
    pet.do_action("dance")
    game = None


def pick_food():
  global picker
  if badge.pressed(BUTTON_BACK) or badge.pressed(BUTTON_UP):
    picker = None
    return
  if badge.pressed(BUTTON_LEFT):
    picker.move(-1)
  if badge.pressed(BUTTON_RIGHT):
    picker.move(1)
  if badge.pressed(BUTTON_SELECT):
    effect = picker.choice()[4]
    for stat, amount in effect.items():
      getattr(pet, stat)(amount)
    pet.do_action("eat")
    picker = None


def play():
  """Look after him until he goes."""
  global stats_shown, game, picker

  while pet.alive():
    busy = game is not None or picker is not None

    # move his day on, 100x faster while UP is held
    speed = WARP if not busy and badge.held(BUTTON_UP) else 1
    passed = clock.advance(badge.ticks_delta / 1000 * speed)

    # DOWN shows her walk and hides it again
    if not busy and badge.pressed(BUTTON_DOWN):
      stats_shown = not stats_shown
      if stats_shown:
        pet.move_to(WALK_SPOT)

    # the watch may have sent new steps: they turn into meals
    if badge.ticks - steps_checked[0] >= WALK_CHECK_S * 1000:
      steps_checked[0] = badge.ticks
      steps.reload()
      feed_from_steps()

    hour, minute = clock.now()

    # he turns in for the night by himself, and nothing rouses him early
    if clock.phase(hour) == "night":
      pet.set_mood("sleep")
      game = picker = None
    else:
      # every need falls away as his day goes by
      if not busy:
        pet.happy(-(passed / (HAPPY_HOURS * 60)) * 100)
        pet.hunger(-(passed / (HUNGER_HOURS * 60)) * 100)
        pet.clean(-(passed / (CLEAN_HOURS * 60)) * 100)

      if game is not None:
        play_game()
      elif picker is not None:
        pick_food()
      else:
        choose_button()

        # left to himself he crosses to a new spot and finds something to do,
        # unless she is showing her walk
        if not stats_shown and pet.time_since_last_position_change() > 20:
          pet.set_mood("run")
          pet.move_to_random()

        if pet.time_since_last_mood_change() > 8:
          pet.random_idle()

    pet.update()
    draw(hour, minute)
    badge.update()


def game_over():
  """He is gone. Hold the scene until Enter asks for another."""
  # nothing of him is kept, so the badge opens on the titles next time
  State.delete("tufty")

  # she goes at once, whatever she was in the middle of
  pet.do_action(None)
  pet.set_mood("dead")
  pet.set_speed(1)
  pet.move_to_center()

  while True:
    clock.advance(badge.ticks_delta / 1000)
    pet.update()
    draw(*clock.now())
    badge.update()

    if badge.pressed(BUTTON_SELECT):
      return


def feed_from_steps():
  if pet.alive() and steps.feed(pet):
    pet.do_action("eat")


def save_state():
  saved = pet.save()
  saved["clock"] = clock.reading()
  State.save("tufty", saved)


def get_state():
  """His stats and clock as they were saved, or None if no Tufty is waiting."""
  state = {}
  State.load("tufty", state)
  return state or None


def on_exit():
  # nobody is out while the titles are up, so there is nothing to keep
  if pet is None:
    return

  if pet.alive():
    save_state()
  else:
    State.delete("tufty")


saved = get_state()
pet = None
steps = walk.Walk()
steps_checked = [0]

while True:
  # a Tufty already in hand skips the titles
  if not saved:
    titles()

  # 95 is the ground he stands on
  pet = tufty.Tufty(95)
  if saved:
    # and picks his day up where he left it
    pet.load(saved)
    clock.resume(saved["clock"])
    saved = None

  # the steps walked since she was last seen are waiting for her
  feed_from_steps()

  save_state()
  play()
  game_over()
  pet = None
