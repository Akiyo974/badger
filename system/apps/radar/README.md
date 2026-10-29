# Radar

Radar shows nearby Badger devices as dots on the badge screen and an optional IS31FL3741 RGB matrix. It starts in the normal radar view; the Hot / Cold game is opt-in.

## Controls

| View | Controls |
|---|---|
| Radar | **Select** opens the list; **Right** opens encounter history |
| List | **Up / Down** selects a badge; **Right** starts Hot / Cold for that badge; **Select / Left** returns to the radar |
| Hot / Cold | **Select** confirms "Found!"; **Left** quits; after finishing, **Select / Left** returns to the list |
| History | **Up / Down** scrolls; **Select / Left** returns to the radar |

## Proximity and detection

The labelled rings and list use **Very near**, **Near**, and **Far**, never metres. These are relative signal-strength bands, not measured distance. Bodies, walls, orientation and interference all affect Bluetooth signal strength. Angles are fixed positions derived from badge IDs, not directions.

Radar filters unrelated Bluetooth advertisements before queuing them, coalesces repeated packets, and prioritises identity packets when its bounded queue fills. It associates names with both Bluetooth address and address type, accepts stock badge advertisements, and rejects unsupported Radar protocol versions. A three-sample median, time-based smoothing and hysteresis reduce jumps between proximity bands.

After **4 seconds** without a packet, a badge is marked **Fading** and progressively dims on screen, on the matrix and in the case-light feedback. It is removed after **12 seconds**. A new packet restores its visibility. Fresh badges take priority over fading ones in the nearby list.

Bluetooth scanning and advertising require the Universe 2026 badge firmware. Stock badges are visible while running Contacts, Pong or Merge Conflict; Radar badges are visible while Radar is open.

## Hot / Cold game

Choose a badge in the list and press **Right** to play. A gauge, **Cold / Warm / Hot** labels and a **Warmer / Colder / Steady** trend help you follow its signal. Case lights and the optional matrix follow only the selected badge; the optional motor pulses more frequently as its signal gets stronger.

The game never starts automatically and never declares a win from signal strength. Press **Select** yourself when you find the person: **Found!** shows your elapsed time. If the target stops advertising, the game waits for that same badge instead of switching targets. Vibration guidance pauses when its signal becomes stale.

## Encounter history

The **200 most recently encountered distinct badges** are kept in `/state/radar_history.json`, across launches and restarts. Each entry contains the badge ID, last received name/status/app, and visit count. A visit means a detection after launch or after the badge has been absent for at least 12 seconds; repeated advertisements do not add visits. This is a detection history, **not proof of a meeting or a contact exchange**.

Changed entries are saved at most once every 10 seconds, and on normal exit, to limit flash writes. Abrupt power loss can lose the most recent unsaved changes. No wall-clock dates are invented when the badge clock is unset. Load/save errors are printed to the serial console and indicated in the UI.

## Optional hardware

The external matrix is supported when a 13×9 RGB matrix using the IS31FL3741 is connected to the Qw/ST I²C port at address `0x30`. It shows the radar sweep and nearby badges, with colors identifying Radar, Contacts, Pong, and other apps. Its global current is limited to `0x40`, and the driver's previous register values are restored when Radar exits.

With a DRV2605 or DRV2605L haptic driver at I²C address `0x5A` and an ERM vibration motor, Radar gives a short vibration for new arrivals. Simultaneous arrivals are coalesced rather than building a long vibration backlog. During Hot / Cold, pulses guide you towards the selected target instead. The motor is configured for the Adafruit-style ERM motor.

## Development

Run `py tests/test_radar.py` from the repository root. The simulated firmware tests cover packet filtering and bursts, stock interoperability, address changes, smoothing, fading, history persistence and the opt-in game. Actual radio range and feedback still depend on the badge and its environment.
