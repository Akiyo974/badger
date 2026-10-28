package com.christendijoux.badgerremote

import androidx.annotation.StringRes
import java.util.UUID

/**
 * What the badge expects (system/remote.py): one GATT write of 2 bytes per
 * command, the action then the button.
 */
object Protocol {
    val SERVICE: UUID = UUID.fromString("6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001")
    val COMMAND: UUID = UUID.fromString("6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001")

    /** A held button is repeated this often; the badge lets go after 1.5 s of silence. */
    const val HOLD_REPEAT_MS = 500L

    fun encode(action: Action, button: BadgeButton): ByteArray =
        byteArrayOf(action.code.toByte(), button.code.toByte())
}

enum class Action(val code: Int) {
    /** Pressed, then released on the next frame. */
    TAP(0),

    /** Held until [UP], or until the watch goes quiet. */
    DOWN(1),
    UP(2),
}

/** The badge's buttons, in the order of BUTTONS in system/main.py. */
enum class BadgeButton(val code: Int, @StringRes val label: Int) {
    UP(0, R.string.button_up),
    DOWN(1, R.string.button_down),
    LEFT(2, R.string.button_left),
    RIGHT(3, R.string.button_right),
    SELECT(4, R.string.button_select),
    BACK(5, R.string.button_back),
    HOME(6, R.string.button_home),
}
