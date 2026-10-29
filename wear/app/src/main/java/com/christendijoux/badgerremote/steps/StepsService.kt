package com.christendijoux.badgerremote.steps

import android.content.Context
import android.os.SystemClock
import android.util.Log
import androidx.concurrent.futures.await
import androidx.health.services.client.HealthServices
import androidx.health.services.client.PassiveListenerService
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.PassiveListenerConfig
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * Receives the watch's steps from Health Services, in the background, even
 * while the app is closed: the day's total, and the steps of each interval,
 * added up per hour.
 */
class StepsService : PassiveListenerService() {
    override fun onNewDataPointsReceived(dataPoints: DataPointContainer) {
        val boot = bootInstant()
        Log.d(TAG, "steps ${dataPoints.getData(DataType.STEPS).sumOf { it.value }}, daily " +
            dataPoints.getData(DataType.STEPS_DAILY).joinToString { "${it.value} until ${it.getEndInstant(boot)}" })
        val store = StepStore(this)
        store.save(StepCounting.add(store.today(), dataPoints, boot))
    }

    companion object {
        private const val TAG = "BadgerSteps"
        private val DATA_TYPES = setOf(DataType.STEPS, DataType.STEPS_DAILY)

        /** Starts (or restarts, after a reboot) the background listening. */
        suspend fun register(context: Context): Boolean {
            val client = HealthServices.getClient(context).passiveMonitoringClient
            val capabilities = client.getCapabilitiesAsync().await()
            val types = DATA_TYPES.intersect(capabilities.supportedDataTypesPassiveMonitoring)
            if (types.isEmpty()) return false
            val config = PassiveListenerConfig.builder().setDataTypes(types).build()
            client.setPassiveListenerServiceAsync(StepsService::class.java, config).await()
            Log.d(TAG, "listening to $types")
            return true
        }

        /** Asks Health Services for the data it has not delivered yet. */
        suspend fun flush(context: Context) {
            HealthServices.getClient(context).passiveMonitoringClient.flushAsync().await()
        }

        private fun bootInstant(): Instant =
            Instant.ofEpochMilli(System.currentTimeMillis() - SystemClock.elapsedRealtime())
    }
}

/** How the data points add up to [DaySteps], apart from Android for the tests. */
object StepCounting {
    fun add(
        day: DaySteps,
        dataPoints: DataPointContainer,
        boot: Instant,
        zone: ZoneId = ZoneId.systemDefault(),
    ): DaySteps {
        val intervals = dataPoints.getData(DataType.STEPS).map { point ->
            Interval(point.getStartInstant(boot), point.getEndInstant(boot), point.value)
        }
        val daily = dataPoints.getData(DataType.STEPS_DAILY).maxByOrNull { it.endDurationFromBoot }?.let {
            Interval(it.getStartInstant(boot), it.getEndInstant(boot), it.value)
        }
        return add(day, intervals, daily, zone)
    }

    data class Interval(val start: Instant, val end: Instant, val steps: Long)

    fun add(day: DaySteps, intervals: List<Interval>, daily: Interval?, zone: ZoneId): DaySteps {
        var current = day
        for (interval in intervals.sortedBy { it.end }) {
            // Each interval counts for the hour of its middle (they last a few minutes)
            val middle = interval.start.plusMillis((interval.end.toEpochMilli() - interval.start.toEpochMilli()) / 2)
            val at = LocalDateTime.ofInstant(middle, zone)
            if (at.toLocalDate() != current.date) {
                if (at.toLocalDate() < current.date) continue
                current = DaySteps.empty(at.toLocalDate())
            }
            val hours = current.hours.toMutableMap()
            hours[at.hour] = (hours[at.hour] ?: 0) + interval.steps
            current = current.copy(hours = hours, total = maxOf(current.total, hours.values.sum()))
        }
        if (daily != null) {
            val date = LocalDateTime.ofInstant(daily.end, zone).toLocalDate()
            if (date > current.date) current = DaySteps.empty(date)
            if (date == current.date) current = current.copy(total = maxOf(daily.steps, current.hours.values.sum()))
        }
        return current
    }
}
