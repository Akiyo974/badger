package com.christendijoux.badgerremote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.lifecycleScope
import com.christendijoux.badgerremote.ui.RemoteScreen

class MainActivity : ComponentActivity() {
    private lateinit var link: BadgeLink

    private val permissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        if (link.hasPermissions()) restart()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        link = BadgeLink(applicationContext, lifecycleScope)
        if (!link.hasPermissions()) askPermissions()
        setContent {
            val state by link.state.collectAsState()
            RemoteScreen(
                state = state,
                onSend = link::send,
                onForget = link::forget,
                onAskPermission = ::askPermissions,
            )
        }
    }

    // Connected only while the app is on screen: no Bluetooth in the background
    override fun onStart() {
        super.onStart()
        link.start()
    }

    override fun onStop() {
        link.stop()
        super.onStop()
    }

    private fun askPermissions() = permissions.launch(BadgeLink.requiredPermissions())

    private fun restart() {
        link.stop()
        link.start()
    }
}
