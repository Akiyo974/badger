package com.christendijoux.badgerremote.steps

import android.content.Context
import android.content.SharedPreferences
import java.time.LocalDate
import java.time.LocalDateTime

/**
 * The day's steps on the watch: the total Health Services keeps for the day,
 * and the steps per hour this app has recorded since it started listening.
 */
data class DaySteps(
    val date: LocalDate,
    val total: Long,
    /** Steps per hour of [date]; hours before the app started listening are missing. */
    val hours: Map<Int, Long>,
) {
    /** The first and last hour with a count, every hour in between included. */
    fun hourRange(): IntRange? {
        if (hours.isEmpty()) return null
        return hours.keys.min()..hours.keys.max()
    }

    companion object {
        fun empty(date: LocalDate) = DaySteps(date, 0, emptyMap())
    }
}

/** Kept in SharedPreferences, written by [StepsService] and read by the app. */
class StepStore(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("steps", Context.MODE_PRIVATE)

    fun today(now: LocalDateTime = LocalDateTime.now()): DaySteps {
        val date = now.toLocalDate()
        if (prefs.getString(KEY_DATE, null) != date.toString()) return DaySteps.empty(date)
        val hours = (0..23).mapNotNull { hour ->
            val count = prefs.getLong(KEY_HOUR + hour, -1)
            if (count >= 0) hour to count else null
        }.toMap()
        return DaySteps(date, prefs.getLong(KEY_TOTAL, 0), hours)
    }

    /** Saves [steps] if it is today's, starting a new day when the date moved on. */
    fun save(steps: DaySteps) {
        prefs.edit().apply {
            if (prefs.getString(KEY_DATE, null) != steps.date.toString()) clear()
            putString(KEY_DATE, steps.date.toString())
            putLong(KEY_TOTAL, steps.total)
            for ((hour, count) in steps.hours) putLong(KEY_HOUR + hour, count)
        }.apply()
    }

    fun listen(onChange: () -> Unit): SharedPreferences.OnSharedPreferenceChangeListener {
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ -> onChange() }
        prefs.registerOnSharedPreferenceChangeListener(listener)
        return listener
    }

    fun stopListening(listener: SharedPreferences.OnSharedPreferenceChangeListener) {
        prefs.unregisterOnSharedPreferenceChangeListener(listener)
    }

    private companion object {
        const val KEY_DATE = "date"
        const val KEY_TOTAL = "total"
        const val KEY_HOUR = "hour_"
    }
}
