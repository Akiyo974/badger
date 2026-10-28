package com.christendijoux.badgerremote

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class ProtocolTest {
    @Test
    fun encodesActionThenButton() {
        assertArrayEquals(byteArrayOf(0, 0), Protocol.encode(Action.TAP, BadgeButton.UP))
        assertArrayEquals(byteArrayOf(1, 4), Protocol.encode(Action.DOWN, BadgeButton.SELECT))
        assertArrayEquals(byteArrayOf(2, 6), Protocol.encode(Action.UP, BadgeButton.HOME))
    }

    // system/main.py passes the buttons in this order: the codes must not move
    @Test
    fun buttonCodesMatchTheBadge() {
        assertEquals(
            listOf("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK", "HOME"),
            BadgeButton.entries.sortedBy { it.code }.map { it.name },
        )
        assertEquals((0..6).toList(), BadgeButton.entries.map { it.code })
    }
}
