"""
Steps from the watch feed Mona: every 500 steps of the day is a meal, and the
more she walks, the happier she gets.

The steps are the last ones Badger Remote sent (/state/watch_steps). The meals
already given are kept apart from her save (mona_pet_walk), so a new Mona does
not eat the same steps twice.
"""
from badgeware import State

STEPS_STATE = "watch_steps"
WALK_STATE = "mona_pet_walk"
STEPS_PER_MEAL = 500
MEAL_FOOD = 15
MEAL_FUN = 5

# (fewest steps, mood) from the top down
MOODS = (
  (8000, "OVER THE MOON"),
  (4000, "VERY HAPPY"),
  (2000, "HAPPY"),
  (500, "PERKING UP"),
  (0, "SLEEPY"),
)

PANEL = rect(50, 18, 108, 86)
BAR_W = 46
BAR_H = 4
LABEL = color.rgb(150, 150, 160)
VALUE = color.rgb(240, 240, 244)
TRACK = color.rgb(40, 40, 46)
FOOD = color.rgb(57, 211, 83)
FUN = color.rgb(219, 68, 158)
CLEAN = color.rgb(242, 193, 62)
MOOD = color.rgb(95, 237, 131)


def load_steps():
  record = {}
  State.load(STEPS_STATE, record)
  return record or None


def mood(steps):
  for fewest, name in MOODS:
    if steps >= fewest:
      return name
  return MOODS[-1][1]


def meals(steps):
  return steps // STEPS_PER_MEAL


def grouped(number):
  digits = str(number)
  groups = []
  while len(digits) > 3:
    groups.insert(0, digits[-3:])
    digits = digits[:-3]
  groups.insert(0, digits)
  return " ".join(groups)


class Walk:
  def __init__(self):
    self.record = load_steps()
    saved = {}
    State.load(WALK_STATE, saved)
    self.date = saved.get("date")
    self.given = saved.get("meals", 0)

  def steps(self):
    return self.record["steps"] if self.record else 0

  def reload(self):
    self.record = load_steps()

  def feed(self, pet):
    """Gives Mona the meals her steps earned since last time. Returns how many."""
    if self.record is None:
      return 0
    date = list(self.record["date"])
    if date != self.date:
      # a new day: its meals start from none
      self.date, self.given = date, 0
    owed = meals(self.record["steps"]) - self.given
    if owed <= 0:
      return 0
    pet.hunger(owed * MEAL_FOOD)
    pet.happy(owed * MEAL_FUN)
    self.given += owed
    State.save(WALK_STATE, {"date": self.date, "meals": self.given})
    return owed

  def draw(self, pet):
    """The walk panel, beside Mona: steps, her needs, meals and mood."""
    screen.pen = color.rgb(18, 16, 28, 215)
    screen.shape(shape.rounded_rectangle(PANEL.x, PANEL.y, PANEL.w, PANEL.h, 4))
    x = PANEL.x + 5
    screen.pen = LABEL
    screen.text("STEPS TODAY", x, PANEL.y + 4)
    screen.pen = VALUE
    screen.text(grouped(self.steps()) if self.record else "-", x, PANEL.y + 13)

    y = PANEL.y + 24
    for name, value, pen in (("FOOD", pet.hunger(), FOOD), ("FUN", pet.happy(), FUN), ("CLEAN", pet.clean(), CLEAN)):
      screen.pen = LABEL
      screen.text(name, x, y)
      left = PANEL.x + PANEL.w - 5 - BAR_W
      screen.pen = TRACK
      screen.rectangle(left, y + 2, BAR_W, BAR_H)
      screen.pen = pen
      screen.rectangle(left, y + 2, round(BAR_W * value / 100), BAR_H)
      y += 9

    # ark is about 6 pixels a letter: the rule takes two lines
    screen.pen = LABEL
    screen.text("EVERY %d STEPS" % STEPS_PER_MEAL, x, y + 2)
    screen.text("A MEAL: %d TODAY" % meals(self.steps()), x, y + 11)
    screen.pen = MOOD
    feeling = mood(self.steps())
    labelled = "MOOD " + feeling
    if screen.measure_text(labelled)[0] <= PANEL.w - 10:
      feeling = labelled
    screen.text(feeling, x, y + 22)

  def strip_text(self):
    if self.record is None:
      return "OPEN BADGER REMOTE TO SYNC"
    return "KEEP WALKING TO FEED MONA"
