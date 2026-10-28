"""Radar behavior with a simulated MonaOS/BLE environment: py tests/test_radar.py."""
import copy
import json
import pathlib
import struct
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "system" / "apps" / "radar" / "__init__.py"


class FakeState:
    def __init__(self):
        self.saved = {}
        self.writes = 0
        self.fail_save = False

    def load(self, key, defaults):
        defaults.update(copy.deepcopy(self.saved.get(key, {})))

    def save(self, key, value):
        if self.fail_save:
            raise OSError("flash unavailable")
        self.saved[key] = copy.deepcopy(value)
        self.writes += 1


class FakeBadge:
    def __init__(self):
        self.ticks = 0
        self.buttons = set()
        self.light = 0

    def mode(self, mode):
        pass

    def pressed(self, button):
        return button in self.buttons

    def caselights(self, value):
        self.light = value


class FakeBLE:
    def __init__(self):
        self.scans = []
        self.adverts = []
        self.configuration = {}

    def active(self, enabled):
        self.enabled = enabled

    def config(self, **kwargs):
        self.configuration.update(kwargs)

    def irq(self, callback):
        self.callback = callback

    def gap_scan(self, *args):
        self.scans.append(args)

    def gap_advertise(self, *args, **kwargs):
        self.adverts.append((args, kwargs))

    def gap_disconnect(self, handle):
        self.callback(2, (handle, 0, b"phone!"))


def manufacturer(body):
    return bytes((len(body) + 1, 0xFF)) + body


def identity(badge_id, version=1, stock=False, game=11):
    body = (b"\xff\xffBL" + bytes((version,)) + struct.pack("<H", game) if stock
            else b"\xff\xffRD" + bytes((version,)))
    return b"\x02\x01\x06" + manufacturer(body + badge_id)


def text_response(name, status="", stock=False):
    body = b"\x00\xffN" + name.encode() if stock else b"\xff\xffRS" + (name + "|" + status).encode()
    return manufacturer(body)


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.state = FakeState()
        self.badge = FakeBadge()
        self.ble = FakeBLE()
        self.screen = MagicMock()
        self.screen.alpha = 255
        self.screen.measure_text.side_effect = lambda text, font_size=16: (len(text) * font_size / 2, font_size)
        self.icon_alphas = []
        link = types.SimpleNamespace(
            ID_LEN=8,
            game_code=lambda name: {"contacts": 11, "pong": 12, "merge conflict": 13}[name],
            badge_name=lambda badge_id: "badge " + badge_id[-2:].hex(),
            badge_id_hex=lambda badge_id: badge_id.hex(),
            draw_identicon=lambda screen, *args: self.icon_alphas.append(screen.alpha),
        )
        self.bus = MagicMock()
        self.bus.scan.return_value = []
        modules = {
            "bluetooth": types.SimpleNamespace(BLE=lambda: self.ble),
            "machine": types.SimpleNamespace(I2C=lambda: self.bus, unique_id=lambda: b"mybadge!"),
            "missing_details": types.SimpleNamespace(mona_sans=lambda: "font"),
            "badgeware": types.SimpleNamespace(State=self.state, link=link),
            "secrets": types.SimpleNamespace(CONTACT_NAME="Test Badge", RADAR_STATUS="Testing"),
        }
        patcher = patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ns = {
            "__name__": "radar_test", "badge": self.badge, "screen": self.screen,
            "image": types.SimpleNamespace(X2=2), "color": types.SimpleNamespace(rgb=lambda *args: args),
            "shape": MagicMock(), "vec2": lambda x, y: (x, y), "HIRES": 1, "VSYNC": 2,
            "run": lambda callback: None,
        }
        for button in ("UP", "DOWN", "LEFT", "RIGHT", "SELECT"):
            self.ns["BUTTON_" + button] = button
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), self.ns)
        self.radar = self.ns["radar"]

    def update(self, now, *buttons):
        self.badge.ticks = now
        self.badge.buttons = set(buttons)
        return self.radar.update(now)

    def receive(self, badge_id=b"neighbor", now=0, rssi=-65, addr=b"addr01", addr_type=0,
                adv=None, response=False):
        self.badge.ticks = now
        self.radar.irq(5, (addr_type, addr, 4 if response else 0, rssi,
                           identity(badge_id) if adv is None else adv))

    def peer(self, rssi=-65):
        peer = self.ns["Peer"](b"neighbor", 0)
        peer.heard(rssi, 0)
        return peer

    def test_phone_noise_does_not_consume_queue(self):
        for i in range(1000):
            self.receive(addr=i.to_bytes(6, "little"), adv=b"\x05\x09Test")
        self.assertEqual(len(self.radar.queue), 0)
        self.receive()
        self.assertEqual(len(self.update(1)), 1)

    def test_repeated_packets_are_coalesced_with_receive_time(self):
        for now in range(100):
            self.receive(now=now, rssi=-80 + now // 10)
        self.assertEqual(len(self.radar.queue), 1)
        peer = self.update(500)[0]
        self.assertEqual(peer.seen, 99)
        self.assertEqual(peer.rssi, -71)

    def test_queue_is_bounded_and_identity_takes_priority(self):
        for i in range(self.ns["QUEUE_LIMIT"]):
            self.receive(addr=i.to_bytes(6, "little"), response=True, adv=text_response("Test"))
        self.receive(now=10)
        self.assertEqual(len(self.radar.queue), self.ns["QUEUE_LIMIT"])
        with patch("builtins.print"):
            self.assertIn(b"neighbor", [peer.id for peer in self.update(10)])

    def test_scan_response_before_identity_in_batch_keeps_name(self):
        self.receive(now=10, response=True, adv=text_response("Ada", "Rust"))
        self.receive(now=20)
        peer = self.update(30)[0]
        self.assertEqual((peer.name, peer.status, peer.seen), ("Ada", "Rust", 20))
        self.assertEqual(self.radar.history.entries[0]["visits"], 1)

    def test_orphan_response_is_not_a_badge(self):
        self.receive(response=True, adv=text_response("Ada"))
        self.assertEqual(self.update(10), [])

    def test_address_type_is_part_of_identity_mapping(self):
        self.receive(b"badge001", addr_type=0)
        self.receive(b"badge002", addr_type=1)
        self.assertEqual(len(self.update(10)), 2)
        self.assertEqual(len(self.radar.addresses), 2)

    def test_rotating_address_keeps_one_peer_and_one_visit(self):
        self.receive()
        self.update(1)
        self.receive(now=500, addr=b"addr02")
        self.update(500)
        self.assertEqual(len(self.radar.peers), 1)
        self.assertEqual(list(self.radar.addresses), [(0, b"addr02")])
        self.assertEqual(self.radar.history.entries[0]["visits"], 1)

    def test_batch_processing_does_not_depend_on_dict_iteration_order(self):
        self.receive(now=100, addr=b"addr01")
        self.receive(now=200, addr=b"addr02")
        self.radar.queue = dict(reversed(list(self.radar.queue.items())))
        self.update(300)
        self.assertEqual(list(self.radar.addresses), [(0, b"addr02")])
        self.assertEqual(self.radar.peers[b"neighbor"].seen, 200)

    def test_irq_copies_reused_memoryview_buffers(self):
        address = bytearray(b"addr01")
        advert = bytearray(identity(b"neighbor"))
        self.receive(addr=memoryview(address), adv=memoryview(advert))
        address[:] = bytes(len(address))
        advert[:] = bytes(len(advert))
        self.assertEqual(self.update(1)[0].id, b"neighbor")
        self.assertEqual(list(self.radar.addresses), [(0, b"addr01")])

    def test_invalid_version_length_rssi_and_self_are_ignored(self):
        for adv in (identity(b"neighbor", version=2), manufacturer(b"\xff\xffRD\x01tiny"),
                    b"\x20\xffbroken", b"\x00"):
            self.receive(adv=adv)
        for rssi in (0, 127, -128):
            self.receive(rssi=rssi)
        self.receive(b"mybadge!")
        self.assertEqual(self.update(10), [])

    def test_stock_badges_and_app_switch_remain_compatible(self):
        self.receive()
        self.receive(response=True, adv=text_response("Ada", "Rust"))
        self.update(0)
        self.receive(now=1000, adv=identity(b"neighbor", stock=True, game=12))
        self.receive(now=1000, response=True, adv=text_response("Ada", stock=True))
        peer = self.update(1000)[0]
        self.assertEqual((peer.radar, peer.game, peer.status, peer.name), (False, "pong", "", "Ada"))
        self.receive(now=1100, response=True, adv=text_response("Old name", "Old status"))
        self.update(1100)
        self.assertEqual((peer.name, peer.status, peer.seen), ("Ada", "", 1000))

    def test_expired_queued_packet_does_not_resurrect_a_peer(self):
        self.receive(now=0)
        self.assertEqual(self.update(self.ns["FORGET_MS"]), [])

    def test_known_scan_response_refreshes_presence(self):
        self.receive()
        self.update(0)
        self.receive(now=8000, response=True, adv=text_response("Ada"))
        self.assertEqual(self.update(12000)[0].seen, 8000)

    def test_scan_restarts_and_advertising_recovers_after_connection(self):
        self.radar.irq(6, None)
        self.radar.irq(1, (42, 0, b"phone!"))
        self.update(100)
        self.assertEqual(len(self.ble.scans), 2)
        self.assertEqual(len(self.ble.adverts), 2)
        self.assertEqual(self.ble.configuration["rxbuf"], 2048)

    def test_proximity_boundaries_have_no_metres(self):
        for rssi, expected in ((-95, "Far"), (-76, "Far"), (-75, "Near"),
                               (-61, "Near"), (-60, "Very near"), (-45, "Very near")):
            self.assertEqual(self.peer(rssi).proximity(0), expected)

    def test_signal_spike_is_filtered_and_hysteresis_stops_flicker(self):
        peer = self.peer(-70)
        for now in (200, 400):
            peer.heard(-70, now)
        peer.heard(-30, 600)
        self.assertEqual(peer.rssi, -70)
        peer = self.peer(-61)
        for now in range(100, 4000, 100):
            peer.heard(-59, now)
        self.assertEqual(peer.zone, 1)
        for now in range(4000, 8000, 100):
            peer.heard(-55, now)
        self.assertEqual(peer.zone, 2)

    def test_silence_fades_then_expires_without_jump(self):
        self.receive()
        peer = self.update(0)[0]
        for now, expected in ((0, 1), (4000, 1), (8000, 0.5), (11920, 0.01), (12000, 0)):
            self.assertAlmostEqual(peer.visibility(now), expected)
        self.assertEqual(peer.proximity(8000), "Fading")
        self.assertEqual(len(self.update(11999)), 1)
        self.assertEqual(self.update(12000), [])
        self.assertEqual(self.radar.addresses, {})

    def test_reacquisition_resets_stale_filter(self):
        peer = self.peer(-90)
        peer.heard(-50, 5000)
        self.assertEqual(peer.rssi, -50)
        self.assertEqual(peer.proximity(5000), "Very near")
        self.assertEqual(peer.visibility(5000), 1)

    def test_fade_is_applied_to_screen_matrix_and_case_lights(self):
        self.receive(rssi=-65)
        peers = self.update(500)
        early_light = self.badge.light
        peers = self.update(8000)
        self.assertLess(self.badge.light, early_light)
        self.radar.draw(peers, 8000)
        self.assertIn(127, self.icon_alphas)
        self.assertEqual(self.screen.alpha, 255)
        self.radar.view = "list"
        self.radar.draw(peers, 8000)
        self.assertEqual(self.screen.alpha, 255)
        matrix = self.radar.matrix
        matrix.available = True
        matrix.write_page = MagicMock()
        peer = peers[0]
        peer.angle = 0
        matrix.render(peers, 8000)
        x = 6 + round(max(1, round((1 - peer.closeness) * 4)) * 1.4)
        blue = matrix.channel_addresses(x, 4)[2]
        self.assertEqual(matrix.last_frame[blue], int((80 + peer.closeness * 175) * 0.5))

    def test_closest_dot_does_not_cover_self(self):
        radius = self.ns["signal_radius"](1)
        self.assertGreater(radius, self.ns["DOT_SIZE"] / 2 + 8)

    def test_history_counts_encounters_not_packets_and_persists(self):
        self.receive()
        self.update(0)
        for now in (100, 200, 300):
            self.receive(now=now, response=True, adv=text_response("Ada", "Rust"))
            self.update(now)
        self.assertEqual(self.radar.history.entries[0]["visits"], 1)
        self.update(12300)
        self.receive(now=13000)
        self.update(13000)
        self.radar.close()
        history = self.ns["EncounterHistory"]()
        self.assertEqual(history.entries[0]["visits"], 2)
        self.assertEqual((history.entries[0]["name"], history.entries[0]["status"]), ("Ada", "Rust"))
        self.assertIn("radar_history", self.state.saved)
        self.assertFalse(history.dirty)

    def test_history_is_limited_to_200_distinct_recent_badges(self):
        history = self.radar.history
        for number in range(201):
            peer = self.ns["Peer"](number.to_bytes(8, "little"), 0)
            history.observe(peer, True)
        self.assertEqual(len(history.entries), 200)
        self.assertEqual(len(history.by_id), 200)
        self.assertEqual(history.entries[0]["id"], (200).to_bytes(8, "little").hex())
        self.assertNotIn(bytes(8).hex(), history.by_id)
        history.save(0, force=True)
        self.assertEqual(len(self.ns["EncounterHistory"]().entries), 200)

    def test_history_writes_are_batched_and_failures_are_reported(self):
        history = self.radar.history
        history.observe(self.peer(), True)
        history.save(9999)
        self.assertEqual(self.state.writes, 0)
        self.state.fail_save = True
        with patch("builtins.print") as log:
            history.save(10000)
        self.assertTrue(history.dirty)
        self.assertIsNotNone(history.error)
        log.assert_called_once()
        self.state.fail_save = False
        history.save(20000)
        self.assertFalse(history.dirty)
        self.assertIsNone(history.error)
        history.save(30000)
        self.assertEqual(self.state.writes, 1)

    def test_invalid_history_is_visible_as_an_error(self):
        self.state.saved["radar_history"] = {"entries": [{"id": "broken"}]}
        with patch("builtins.print"):
            history = self.ns["EncounterHistory"]()
        self.assertEqual(history.entries, [])
        self.assertIsNotNone(history.error)

    def test_game_is_opt_in_and_selection_tracks_identity_not_rank(self):
        self.receive(b"badge001", rssi=-80, addr=b"addr01")
        self.receive(b"badge002", rssi=-50, addr=b"addr02")
        self.update(0)
        self.assertEqual(self.radar.view, "radar")
        self.assertIsNone(self.radar.game)
        self.update(10, "SELECT")
        self.update(20)
        self.update(30, "DOWN")
        self.assertEqual(self.radar.selected_id, b"badge001")
        self.radar.peers[b"badge001"].rssi = -40
        self.update(40, "RIGHT")
        self.assertEqual(self.radar.game.target_id, b"badge001")
        self.update(100000)
        self.assertIsNone(self.radar.game.finished)

    def test_game_uses_only_target_and_waits_for_same_badge_after_signal_loss(self):
        self.receive(b"badge001", rssi=-80, addr=b"addr01")
        self.receive(b"badge002", rssi=-40, addr=b"addr02")
        self.update(0)
        self.radar.game = self.ns["HuntGame"](self.radar.peers[b"badge001"], 0)
        self.receive(b"badge002", now=13000, rssi=-40, addr=b"addr02")
        self.update(13000)
        self.assertEqual(self.badge.light, 0)
        self.assertFalse(self.radar.haptics.pending)
        self.assertEqual(self.radar.game.target_id, b"badge001")
        self.receive(b"badge001", now=14000, rssi=-50, addr=b"addr01")
        self.update(14000)
        self.assertGreater(self.badge.light, 0)
        self.assertIsNone(self.radar.game.finished)

    def test_game_manual_found_timer_and_exit(self):
        self.receive()
        peer = self.update(0)[0]
        self.radar.game = self.ns["HuntGame"](peer, 0)
        self.update(3200, "SELECT")
        self.assertEqual(self.radar.game.finished, 3200)
        self.assertEqual(self.radar.game.elapsed(9999), 3)
        self.radar.draw(self.radar.nearby(3200), 3200)
        self.update(4000, "SELECT")
        self.assertIsNone(self.radar.game)
        self.assertEqual(self.radar.view, "list")
        self.radar.game = self.ns["HuntGame"](peer, 4000)
        self.update(4500, "LEFT")
        self.assertIsNone(self.radar.game)

    def test_game_feedback_and_haptics_do_not_build_a_backlog(self):
        haptics = self.radar.haptics
        haptics.available = True
        for _ in range(200):
            haptics.queue()
        haptics.update(0)
        self.assertFalse(haptics.pending)
        peer = self.peer(-80)
        game = self.ns["HuntGame"](peer, 0)
        game.update(peer, 500, haptics)
        far_interval = game.next_buzz - 500
        peer.rssi = -45
        peer.seen = 2500
        game.update(peer, 2500, haptics)
        self.assertEqual(game.trend, "Warmer")
        self.assertLess(game.next_buzz - 2500, far_interval)
        game.update(peer, 7000, haptics)
        self.assertFalse(haptics.pending)

    def test_history_controls_and_all_views_draw_without_hardware(self):
        self.receive()
        peers = self.update(0)
        self.update(1, "RIGHT")
        self.assertEqual(self.radar.view, "history")
        self.radar.draw(peers, 1)
        self.update(2, "LEFT")
        self.assertEqual(self.radar.view, "radar")
        self.radar.draw(peers, 2)
        self.update(3, "SELECT")
        self.update(4)
        self.radar.draw(peers, 4)
        self.update(5, "RIGHT")
        self.radar.draw(peers, 5)
        self.radar.draw([], 5000)
        self.update(13000)
        self.radar.draw([], 13000)
        self.assertEqual(self.screen.alpha, 255)

    def test_advertisement_and_utf8_text_stay_in_legacy_ble_limits(self):
        self.radar.my_name = "Long name with | separator"
        self.radar.my_status = "\u00e9" * 30
        self.radar.advertise()
        _, packet = self.ble.adverts[-1]
        self.assertLessEqual(len(packet["adv_data"]), 31)
        self.assertLessEqual(len(packet["resp_data"]), 31)
        fields = list(self.ns["fields"](packet["resp_data"]))
        text = fields[0][1][4:].decode("utf-8")
        self.assertEqual(text.count("|"), 1)

    def test_screenshot_scenarios_never_save_demo_encounters(self):
        captures = SOURCE.parents[3] / "docs" / "screenshots" / "captures.json"
        for capture in json.loads(captures.read_text(encoding="utf-8")):
            if capture["app"] != "radar":
                continue
            with self.subTest(file=capture["file"]):
                self.badge.ticks = 0
                self.radar = self.ns["radar"] = self.ns["Radar"]()
                exec(capture["setup"], {"g": self.ns, "REAL_BADGE": self.badge})
                peers = self.update(1)
                self.assertGreater(len(peers), 0)
                self.radar.draw(peers, 1)
                if self.radar.game is not None:
                    self.assertEqual((peers[0].name, peers[0].status), ("Ada", "Rust"))
                self.update(20000)
                self.radar.close()
                self.assertEqual(self.state.writes, 0)


if __name__ == "__main__":
    unittest.main()
