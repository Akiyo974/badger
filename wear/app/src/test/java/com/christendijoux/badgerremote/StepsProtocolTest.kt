package com.christendijoux.badgerremote

import com.christendijoux.badgerremote.steps.DaySteps
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate
import java.time.LocalDateTime

class StepsProtocolTest {
    private val at = LocalDateTime.of(2026, 10, 28, 14, 32)

    // Same layout as STEPS_HEADER in system/remote.py: <BHBBBBIBB, then u16 per hour
    @Test
    fun encodesHeaderThenHours() {
        val steps = DaySteps(LocalDate.of(2026, 10, 28), 4213, mapOf(9 to 300L, 11 to 1200L))
        val expected = byteArrayOf(
            1, 0xEA.toByte(), 0x07, 10, 28, 14, 32,
            0x75, 0x10, 0, 0,
            9, 3,
            0x2C, 0x01, 0, 0, 0xB0.toByte(), 0x04,
        )
        assertArrayEquals(expected, Protocol.encodeSteps(steps, at, 64))
    }

    @Test
    fun dropsTheHoursWhenTheLinkIsTooSmall() {
        val steps = DaySteps(LocalDate.of(2026, 10, 28), 4213, (0..23).associateWith { 100L })
        val bytes = Protocol.encodeSteps(steps, at, 20)
        assertEquals(13, bytes.size)
        assertEquals(0, bytes[12].toInt())
    }

    @Test
    fun noHistoryMeansNoHours() {
        val bytes = Protocol.encodeSteps(DaySteps(LocalDate.of(2026, 10, 28), 12, emptyMap()), at, 64)
        assertEquals(13, bytes.size)
    }
}
