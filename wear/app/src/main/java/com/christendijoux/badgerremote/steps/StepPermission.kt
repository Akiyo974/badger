package com.christendijoux.badgerremote.steps

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager

/** Physical activity: asked once; if refused, the remote works without steps. */
object StepPermission {
    const val NAME = Manifest.permission.ACTIVITY_RECOGNITION
    private const val KEY_ASKED = "activity_asked"

    fun granted(context: Context): Boolean =
        context.checkSelfPermission(NAME) == PackageManager.PERMISSION_GRANTED

    fun shouldAsk(context: Context): Boolean =
        !granted(context) && !prefs(context).getBoolean(KEY_ASKED, false)

    fun markAsked(context: Context) {
        prefs(context).edit().putBoolean(KEY_ASKED, true).apply()
    }

    private fun prefs(context: Context) = context.getSharedPreferences("steps_permission", Context.MODE_PRIVATE)
}
