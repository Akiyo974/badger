import machine
import sys

MENU_DIR = "/system/apps/menu"
APPS_DIR = "/system/apps"
MENU_MODULES = ("ui", "icons", "gallery", "app", "silhouettes", "achievements", "celebration", "opening", "mona3d", "mona")
preloaded = []

try:
    import sparkle
except Exception as error:  # noqa: BLE001
    sparkle = None
    print("sparkle unavailable:", error)

if machine.reset_cause() != machine.WDT_RESET:
    badge.mode(HIRES | VSYNC)
    sys.path.insert(0, MENU_DIR)
    for name in MENU_MODULES:
        try:
            __import__(name)
            preloaded.append(name)
        except ImportError as error:
            print("menu preload failed:", name, error)
    try:
        sys.modules["app"].shared(APPS_DIR).preload_images()
        sys.modules["mona"].shared()
    except (KeyError, OSError) as error:
        print("menu preload failed:", error)
    sys.path.remove(MENU_DIR)
    launch("/system/startup")

if sparkle is not None:
    try:
        sparkle.start(deferred=True)
    except Exception as error:  # noqa: BLE001
        print("sparkle unavailable:", error)

# Eat the wakeup button press to prevent it leaking into the menu
badge.poll()

# We expect a launcher menu to be at /system/apps/menu
app_to_launch = launch("/system/apps/menu")

for name in preloaded:
    sys.modules.pop(name, None)

# Stopping in Thonny can cause launch("/system/apps/menu") to return None
if app_to_launch is not None:

    # Don't pass menu button presses into the newly launched app
    while badge.pressed() or badge.held() or badge.released():
        badge.poll()

    launch(app_to_launch)

# Catch any exit and reset back to the launcher
reset()
