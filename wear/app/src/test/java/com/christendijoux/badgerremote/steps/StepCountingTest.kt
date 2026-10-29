package com.christendijoux.badgerremote.steps

import com.christendijoux.badgerremote.steps.StepCounting.Interval
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset

class StepCountingTest {
    private val zone: ZoneId = ZoneOffset.ofHours(-7)
    private val day = LocalDate.of(2026, 10, 28)

    private fun interval(hour: Int, minute: Int, steps: Long) = Interval(
        LocalDateTime.of(day, java.time.LocalTime.of(hour, minute)).atZone(zone).toInstant(),
        LocalDateTime.of(day, java.time.LocalTime.of(hour, minute + 2)).atZone(zone).toInstant(),
        steps,
    )

    @Test
    fun addsIntervalsUpPerHour() {
        val result = StepCounting.add(
            DaySteps.empty(day),
            listOf(interval(9, 10, 100), interval(9, 40, 50), interval(11, 0, 20)),
            null,
            zone,
        )
        assertEquals(mapOf(9 to 150L, 11 to 20L), result.hours)
        assertEquals(170L, result.total)
    }

    @Test
    fun theDailyTotalWinsWhenItIsBigger() {
        val daily = Interval(day.atStartOfDay(zone).toInstant(), interval(12, 0, 0).end, 4213)
        val result = StepCounting.add(DaySteps.empty(day), listOf(interval(11, 0, 20)), daily, zone)
        assertEquals(4213L, result.total)
        assertEquals(mapOf(11 to 20L), result.hours)
    }

    @Test
    fun aNewDayStartsFromZero() {
        val yesterday = DaySteps(day.minusDays(1), 9000, mapOf(18 to 900L))
        val result = StepCounting.add(yesterday, listOf(interval(9, 0, 30)), null, zone)
        assertEquals(day, result.date)
        assertEquals(mapOf(9 to 30L), result.hours)
        assertEquals(30L, result.total)
    }

    @Test
    fun hourRangeCoversTheGaps() {
        assertEquals(9..11, DaySteps(day, 0, mapOf(9 to 1L, 11 to 2L)).hourRange())
    }
}
