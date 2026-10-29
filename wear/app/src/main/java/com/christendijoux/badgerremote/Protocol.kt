package com.christendijoux.badgerremote

import androidx.annotation.StringRes
import com.christendijoux.badgerremote.steps.DaySteps
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.time.LocalDateTime
import java.util.UUID

/**
 * What the badge expects (system/remote.py): one GATT write of 2 bytes per
 * command, the action then the button.
 */
object Protocol {
    val SERVICE: UUID = UUID.fromString("6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001")
    val COMMAND: UUID = UUID.fromString("6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001")
    val STEPS: UUID = UUID.fromString("6e1d1002-8d5c-4b52-9a57-2a6b4c1b0001")

    /** Big enough for the steps with 24 hourly counts (61 bytes + 3 of ATT header). */
    const val PREFERRED_MTU = 72
    const val DEFAULT_MTU = 23

    /** A held button is repeated this often; the badge lets go after 1.5 s of silence. */
    const val HOLD_REPEAT_MS = 500L

    fun encode(action: Action, button: BadgeButton): ByteArray =
        byteArrayOf(action.code.toByte(), button.code.toByte())

    private const val STEPS_VERSION = 1
    private const val STEPS_HEADER = 13

    /**
     * The day's steps for remote.py's parse_steps(): version, watch date and
     * time, total, then the hourly counts if they fit in [maxBytes].
     */
    fun encodeSteps(steps: DaySteps, at: LocalDateTime, maxBytes: Int): ByteArray {
        val range = steps.hourRange()?.takeIf { STEPS_HEADER + 2 * (it.last - it.first + 1) <= maxBytes }
        val count = range?.let { it.last - it.first + 1 } ?: 0
        val buffer = ByteBuffer.allocate(STEPS_HEADER + 2 * count).order(ByteOrder.LITTLE_ENDIAN)
        buffer.put(STEPS_VERSION.toByte())
        buffer.putShort(at.year.toShort())
        buffer.put(at.monthValue.toByte())
        buffer.put(at.dayOfMonth.toByte())
        buffer.put(at.hour.toByte())
        buffer.put(at.minute.toByte())
        buffer.putInt(steps.total.coerceIn(0, UInt.MAX_VALUE.toLong()).toInt())
        buffer.put((range?.first ?: 0).toByte())
        buffer.put(count.toByte())
        range?.forEach { hour -> buffer.putShort((steps.hours[hour] ?: 0).coerceIn(0, 0xFFFF).toInt().toShort()) }
        return buffer.array()
    }
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
