package com.christendijoux.badgerremote.steps

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Health Services forgets its listeners when the watch restarts: listen again. */
class StepsBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        if (!StepPermission.granted(context)) return
        val pending = goAsync()
        CoroutineScope(Dispatchers.Default).launch {
            try {
                StepsService.register(context.applicationContext)
            } catch (_: Exception) {
                // Nothing to do: the app registers again the next time it opens
            } finally {
                pending.finish()
            }
        }
    }
}
