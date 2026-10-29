package com.christendijoux.badgerremote.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.PointerInputChange
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.min
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Text
import com.christendijoux.badgerremote.Action
import com.christendijoux.badgerremote.BadgeButton
import com.christendijoux.badgerremote.LinkState
import com.christendijoux.badgerremote.Protocol
import com.christendijoux.badgerremote.R
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.NumberFormat

private val Ink = Color(0xFF050505)
private val Paper = Color(0xFFF2F2EE)
private val Accent = Color(0xFF5FED83)
private val Fill = Color(0xFF1E2228)
private val FillPressed = Color(0xFF2E4A36)

private val STEPS_FORMAT: NumberFormat = NumberFormat.getIntegerInstance()

/** Past this, a press becomes a held button (repeated until released). */
private const val LONG_PRESS_MS = 350L

/** Crown rotation, in pixels, for one Up or Down press. */
private const val CROWN_STEP = 60f

/** Where each button sits, as fractions of the screen size from its centre, and how big it is. */
private class Spot(val x: Float, val y: Float, val diameter: Float)

private val SPOTS = mapOf(
    BadgeButton.UP to Spot(0f, -0.225f, 0.21f),
    BadgeButton.LEFT to Spot(-0.245f, 0.02f, 0.21f),
    BadgeButton.SELECT to Spot(0f, 0.02f, 0.21f),
    BadgeButton.RIGHT to Spot(0.245f, 0.02f, 0.21f),
    BadgeButton.DOWN to Spot(0f, 0.265f, 0.21f),
    BadgeButton.BACK to Spot(-0.29f, 0.28f, 0.16f),
    BadgeButton.HOME to Spot(0.29f, 0.28f, 0.16f),
)

/** The day's steps under the buttons, and whether the badge has them. */
data class StepsStatus(val total: Long, val sent: Boolean)

@Composable
fun RemoteScreen(
    state: LinkState,
    steps: StepsStatus?,
    onSend: (Action, BadgeButton) -> Unit,
    onForget: () -> Unit,
    onAskPermission: () -> Unit,
) {
    val connected = state is LinkState.Connected
    KeepScreenOn(connected)
    val focus = remember { FocusRequester() }
    var crown by remember { mutableFloatStateOf(0f) }

    MaterialTheme {
        BoxWithConstraints(
            Modifier
                .fillMaxSize()
                .background(Ink)
                // The crown scrolls like Up / Down on the badge
                .onRotaryScrollEvent { event ->
                    if (connected) {
                        crown += event.verticalScrollPixels
                        while (crown >= CROWN_STEP) {
                            onSend(Action.TAP, BadgeButton.DOWN)
                            crown -= CROWN_STEP
                        }
                        while (crown <= -CROWN_STEP) {
                            onSend(Action.TAP, BadgeButton.UP)
                            crown += CROWN_STEP
                        }
                    }
                    true
                }
                .focusRequester(focus)
                .focusable(),
        ) {
            val size = min(maxWidth, maxHeight)
            Status(state, size, onForget, onAskPermission)
            if (steps != null) Steps(steps, size)
            for ((button, spot) in SPOTS) {
                RemoteButton(button, spot, size, connected, onSend)
            }
        }
    }
    LaunchedEffect(Unit) { focus.requestFocus() }
}

@Composable
private fun Status(state: LinkState, size: Dp, onForget: () -> Unit, onAskPermission: () -> Unit) {
    val text = when (state) {
        LinkState.NoPermission -> stringResource(R.string.grant)
        LinkState.BluetoothOff -> stringResource(R.string.status_off)
        LinkState.Searching -> stringResource(R.string.status_searching)
        is LinkState.Connecting -> stringResource(R.string.status_connecting)
        is LinkState.Connected -> state.name
        LinkState.Lost -> stringResource(R.string.status_error)
    }
    val action: (() -> Unit)? = when (state) {
        LinkState.NoPermission -> onAskPermission
        LinkState.BluetoothOff -> null
        // Also while searching: the remembered badge may be gone for good
        else -> onForget
    }
    val label = when (state) {
        LinkState.NoPermission -> stringResource(R.string.status_no_permission)
        else -> stringResource(R.string.forget)
    }
    Box(Modifier.fillMaxSize()) {
        Text(
            text = text,
            color = if (state is LinkState.Connected || state == LinkState.NoPermission) Accent else Paper.copy(alpha = 0.7f),
            fontSize = 13.sp,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier
                .align(Alignment.Center)
                .offset(y = size * -0.41f)
                .width(size * 0.56f)
                .then(if (action != null) Modifier.clickable(onClickLabel = label, onClick = action) else Modifier),
        )
    }
}

@Composable
private fun Steps(steps: StepsStatus, size: Dp) {
    val text = pluralStringResource(R.plurals.steps_today, steps.total.toInt(), STEPS_FORMAT.format(steps.total))
    Box(Modifier.fillMaxSize()) {
        Text(
            text = if (steps.sent) "$text ✓" else text,
            color = if (steps.sent) Accent else Paper.copy(alpha = 0.7f),
            fontSize = 11.sp,
            textAlign = TextAlign.Center,
            maxLines = 1,
            modifier = Modifier
                .align(Alignment.Center)
                .offset(y = size * 0.43f)
                .width(size * 0.5f),
        )
    }
}

/**
 * One badge button. A quick tap sends TAP; a longer press sends DOWN, repeated
 * while the finger stays, then UP.
 */
@Composable
private fun RemoteButton(
    button: BadgeButton,
    spot: Spot,
    size: Dp,
    enabled: Boolean,
    onSend: (Action, BadgeButton) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val send by rememberUpdatedState(onSend)
    var pressed by remember { mutableStateOf(false) }
    val label = stringResource(button.label)

    Box(Modifier.fillMaxSize()) {
        Canvas(
            Modifier
                .align(Alignment.Center)
                .offset(x = size * spot.x, y = size * spot.y)
                .size(size * spot.diameter)
                .alpha(if (enabled) 1f else 0.35f)
                .clip(CircleShape)
                .background(if (pressed) FillPressed else Fill)
                .semantics {
                    contentDescription = label
                    role = Role.Button
                    onClick {
                        if (enabled) send(Action.TAP, button)
                        enabled
                    }
                }
                .pointerInput(enabled) {
                    if (!enabled) return@pointerInput
                    awaitEachGesture {
                        awaitFirstDown()
                        pressed = true
                        haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        var held = false
                        val repeat = scope.launch {
                            delay(LONG_PRESS_MS)
                            held = true
                            haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                            while (true) {
                                send(Action.DOWN, button)
                                delay(Protocol.HOLD_REPEAT_MS)
                            }
                        }
                        // finally: the gesture is cancelled when the link drops mid-press,
                        // and the repeater must not outlive it
                        var up: PointerInputChange? = null
                        try {
                            up = waitForUpOrCancellation()
                        } finally {
                            repeat.cancel()
                            pressed = false
                            when {
                                held -> send(Action.UP, button)
                                up != null -> send(Action.TAP, button)
                            }
                        }
                    }
                },
        ) {
            drawGlyph(button, if (pressed) Accent else Paper)
        }
    }
}

private fun DrawScope.drawGlyph(button: BadgeButton, color: Color) {
    val w = size.width
    val h = size.height
    val stroke = Stroke(width = w * 0.08f, cap = StrokeCap.Round, join = StrokeJoin.Round)
    when (button) {
        BadgeButton.UP, BadgeButton.DOWN, BadgeButton.LEFT, BadgeButton.RIGHT -> {
            val angle = when (button) {
                BadgeButton.RIGHT -> 90f
                BadgeButton.DOWN -> 180f
                BadgeButton.LEFT -> 270f
                else -> 0f
            }
            // Triangle pointing up, turned towards the button's direction
            val arrow = Path().apply {
                moveTo(w * 0.5f, h * 0.32f)
                lineTo(w * 0.7f, h * 0.62f)
                lineTo(w * 0.3f, h * 0.62f)
                close()
            }
            rotate(angle) { drawPath(arrow, color) }
        }
        BadgeButton.SELECT -> drawCircle(color, radius = w * 0.17f)
        BadgeButton.BACK -> {
            val arrow = Path().apply {
                moveTo(w * 0.68f, h * 0.5f)
                lineTo(w * 0.32f, h * 0.5f)
                moveTo(w * 0.45f, h * 0.36f)
                lineTo(w * 0.31f, h * 0.5f)
                lineTo(w * 0.45f, h * 0.64f)
            }
            drawPath(arrow, color, style = stroke)
        }
        BadgeButton.HOME -> {
            val house = Path().apply {
                moveTo(w * 0.3f, h * 0.5f)
                lineTo(w * 0.5f, h * 0.32f)
                lineTo(w * 0.7f, h * 0.5f)
                moveTo(w * 0.36f, h * 0.46f)
                lineTo(w * 0.36f, h * 0.68f)
                lineTo(w * 0.64f, h * 0.68f)
                lineTo(w * 0.64f, h * 0.46f)
            }
            drawPath(house, color, style = stroke)
        }
    }
}

/** Keeps the screen on while the badge is connected, so the remote stays at hand. */
@Composable
private fun KeepScreenOn(on: Boolean) {
    val view = LocalView.current
    DisposableEffect(on) {
        view.keepScreenOn = on
        onDispose { view.keepScreenOn = false }
    }
}
