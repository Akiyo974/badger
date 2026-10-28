# Radar

Radar shows nearby Badger devices as dots on the badge screen and an optional IS31FL3741 RGB matrix.

Select switches between the radar and list views; Up and Down scroll the list. The external matrix is supported when a 13×9 RGB matrix using the IS31FL3741 is connected to the Qw/ST I²C port at address `0x30`. The matrix shows the radar sweep and nearby badges, with colors identifying Radar, Contacts, Pong, and other apps. Its global current is limited to `0x40`, and the driver's previous register values are restored when Radar exits.

Bluetooth scanning and advertising require the Universe 2026 badge firmware. Bluetooth signal strength estimates distance; it does not provide direction.

With a DRV2605 haptic driver at I²C address `0x5A` on the Qw/ST port and an ERM vibration motor connected to it, Radar gives a short vibration when it first detects a nearby badge. It vibrates again if that badge leaves range and is detected later. The motor is configured for the Adafruit-style ERM motor.
