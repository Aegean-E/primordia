"""Unit tests for the observatory: state payload, dashboard, god-mode shocks and the server."""

import json
import socket
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

from primordia import shocks
from primordia.engine import Engine
from primordia.genome import GENES, Genome, genetic_distance
from primordia.save import SAVE_VERSION, SaveError
from primordia.species import SPECIATION_DISTANCE
from primordia.web import make_server, render_dashboard, serve, state_payload
from primordia.world import LAND, WorldConfig


def small_engine(seed: int = 4, founders: int = 30, **overrides) -> Engine:
    config = WorldConfig(width=16, height=10, day_length=60, food_regrowth=0.12, **overrides)
    return Engine(config=config, seed=seed, founders=founders)


def flat_genome() -> Genome:
    return Genome(genes=tuple(0.5 for _ in GENES))


def land_tile(engine: Engine, skip=lambda x, y: False) -> tuple[int, int]:
    for y in range(engine.config.height):
        for x in range(engine.config.width):
            if engine.world.is_land(x, y) and not skip(x, y):
                return x, y
    raise AssertionError("no matching land tile")


class PayloadTests(unittest.TestCase):
    def test_state_payload_reports_the_living_world(self):
        engine = small_engine()
        for _ in range(120):
            engine.step()
        payload = state_payload(engine)
        self.assertEqual(payload["tick"], 120)
        self.assertEqual(payload["population"], len(engine.creatures))
        self.assertEqual(len(payload["terrain"]), engine.world.length)
        self.assertEqual(len(payload["food"]), engine.world.length)
        self.assertEqual(len(payload["creatures"]), len(engine.creatures))
        self.assertEqual(payload["species_total"], len(engine.registry))
        self.assertGreaterEqual(payload["species_alive"], 1)
        self.assertIn("size", payload["traits"])

    def test_state_payload_is_json_ready(self):
        engine = small_engine()
        engine.step()
        text = json.dumps(state_payload(engine))
        self.assertIn('"tick": 1', text)


class DashboardTests(unittest.TestCase):
    def test_dashboard_carries_the_map_the_tables_and_the_controls(self):
        engine = small_engine()
        for _ in range(60):
            engine.step()
        page = render_dashboard(engine)
        self.assertIn("Primordia", page)
        self.assertIn("population", page)
        self.assertIn("step=100", page)
        for action in ("/god/meteor", "/god/bloom", "/god/cull", "/god/introduce", "/save"):
            self.assertIn(action, page)
        self.assertEqual(page.count('class="tile"'), engine.world.length)

    def test_auto_refresh_is_optional(self):
        engine = small_engine()
        self.assertNotIn("http-equiv", render_dashboard(engine))
        self.assertIn("http-equiv", render_dashboard(engine, auto=2))


class MeteorTests(unittest.TestCase):
    def test_meteor_strips_food_and_kills_within_its_radius(self):
        engine = small_engine(founders=0)
        x, y = land_tile(engine)
        tile = engine.world.index(x, y)
        engine.world.food[tile] = 5.0
        inside = engine.spawn(flat_genome(), x, y, energy=30.0)
        fx, fy = land_tile(engine, skip=lambda tx, ty: max(abs(tx - x), abs(ty - y)) <= 2)
        far_tile = engine.world.index(fx, fy)
        engine.world.food[far_tile] = 5.0
        far = engine.spawn(flat_genome(), fx, fy, energy=30.0)
        report = shocks.meteor(engine, x, y, radius=1)
        self.assertEqual(engine.world.food[tile], 0.0)
        self.assertEqual(engine.world.food[far_tile], 5.0)
        self.assertFalse(inside.alive)
        self.assertNotIn(inside, engine.creatures)
        self.assertTrue(far.alive)
        self.assertGreaterEqual(report.creatures, 1)
        self.assertGreaterEqual(report.tiles, 1)


class BloomTests(unittest.TestCase):
    def test_bloom_raises_food_toward_the_cap_without_passing_it(self):
        engine = small_engine(founders=0)
        x, y = land_tile(engine)
        tile = engine.world.index(x, y)
        engine.world.food[tile] = 0.0
        shocks.bloom(engine, x, y, radius=1, share=1.0)
        self.assertEqual(engine.world.food[tile], engine.world.config.food_cap)
        shocks.bloom(engine, x, y, radius=1, share=1.0)
        self.assertEqual(engine.world.food[tile], engine.world.config.food_cap)


class CullTests(unittest.TestCase):
    def test_cull_removes_the_weakest_share_deterministically(self):
        engine = small_engine(founders=0)
        x, y = land_tile(engine)
        for energy in (10.0, 20.0, 30.0, 40.0):
            engine.spawn(flat_genome(), x, y, energy=energy)
        report = shocks.cull(engine, 0.5)
        self.assertEqual(report.creatures, 2)
        self.assertEqual([creature.energy for creature in engine.creatures], [30.0, 40.0])


class IntroduceTests(unittest.TestCase):
    def test_introduce_releases_near_clones_of_the_founder_lineage(self):
        engine = small_engine(seed=4)
        founder = engine.registry.get(1).founder_genome
        before = len(engine.creatures)
        report = shocks.introduce(engine, 6)
        self.assertEqual(report.creatures, 6)
        self.assertEqual(len(engine.creatures), before + 6)
        for creature in engine.creatures[before:]:
            self.assertEqual(creature.species, 1)
            self.assertLessEqual(genetic_distance(creature.genome, founder), SPECIATION_DISTANCE)


class DiscGeometryTests(unittest.TestCase):
    def test_meteor_and_bloom_sweep_a_disc_not_a_square(self):
        engine = small_engine(founders=0)
        x, y = 8, 5
        for ty in range(3, 8):
            for tx in range(5, 12):
                tile = engine.world.index(tx, ty)
                engine.world.terrain[tile] = LAND
                engine.world.food[tile] = 0.0
        corner = engine.spawn(flat_genome(), x + 2, y + 1, energy=30.0)
        inner = engine.spawn(flat_genome(), x + 1, y + 1, energy=30.0)
        rim = engine.spawn(flat_genome(), x, y + 2, energy=30.0)
        shocks.meteor(engine, x, y, radius=2)
        self.assertTrue(corner.alive)
        self.assertFalse(inner.alive)
        self.assertFalse(rim.alive)
        shocks.bloom(engine, x, y, radius=2, share=1.0)
        cap = engine.world.config.food_cap
        self.assertEqual(engine.world.food[engine.world.index(x + 1, y + 1)], cap)
        self.assertEqual(engine.world.food[engine.world.index(x, y + 2)], cap)
        self.assertEqual(engine.world.food[engine.world.index(x + 2, y + 1)], 0.0)


class ValidationTests(unittest.TestCase):
    def test_shocks_reject_impossible_parameters(self):
        engine = small_engine()
        with self.assertRaises(ValueError):
            shocks.meteor(engine, 0, 0, radius=0)
        with self.assertRaises(ValueError):
            shocks.bloom(engine, -1, 0, radius=1)
        with self.assertRaises(ValueError):
            shocks.cull(engine, 1.5)
        with self.assertRaises(ValueError):
            shocks.introduce(engine, 0)

    def test_shocks_refuse_values_that_are_not_whole_numbers(self):
        engine = small_engine()
        calls = (
            lambda: shocks.meteor(engine, 1.5, 0, radius=1),
            lambda: shocks.meteor(engine, 0, 0, radius=1.5),
            lambda: shocks.bloom(engine, 0.5, 0, radius=1),
            lambda: shocks.introduce(engine, 1.5),
            lambda: shocks.cull(engine, "0.5"),
            lambda: shocks.meteor(engine, True, 0, radius=1),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()


class HttpSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = small_engine()
        for _ in range(40):
            cls.engine.step()
        cls.server = make_server(cls.engine, host="127.0.0.1", port=0, quiet=True)
        cls.thread = threading.Thread(
            target=lambda: cls.server.serve_forever(poll_interval=0.05), daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address[:2]
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_dashboard_state_and_save_are_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            page = response.read().decode("utf-8")
        self.assertIn("Primordia", page)
        with urllib.request.urlopen(self.base + "/state.json", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["width"], 16)
        with urllib.request.urlopen(self.base + "/save", timeout=5) as response:
            save_data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(save_data["version"], SAVE_VERSION)

    def test_favicon_is_answered_quietly(self):
        with urllib.request.urlopen(self.base + "/favicon.ico", timeout=5) as response:
            self.assertEqual(response.status, 204)

    def test_an_oversized_form_body_is_refused(self):
        data = b"pad=" + b"a" * 4096 + b"&share=0.5"
        request = urllib.request.Request(self.base + "/god/cull", data=data)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_step_query_advances_the_clock(self):
        before = self.engine.tick
        with urllib.request.urlopen(self.base + "/?step=5", timeout=5):
            pass
        self.assertEqual(self.engine.tick, before + 5)

    def test_a_malformed_content_length_is_refused_with_the_400_page(self):
        response = self._raw_post(b"Content-Length: not-a-number")
        self.assertIn("400", response.splitlines()[0])
        self.assertIn("Why:", response)
        self.assertIn("Fix:", response)
        with urllib.request.urlopen(self.base + "/state.json", timeout=5) as reply:
            self.assertEqual(reply.status, 200)

    def test_a_negative_content_length_is_refused_instead_of_read_to_eof(self):
        response = self._raw_post(b"Content-Length: -5")
        self.assertIn("400", response.splitlines()[0])
        self.assertIn("Why:", response)
        self.assertIn("Fix:", response)

    def _raw_post(self, header: bytes) -> str:
        host, port = self.server.server_address[:2]
        request = (b"POST /god/cull HTTP/1.1\r\nHost: observatory\r\n"
                   + header + b"\r\n\r\n")
        with socket.create_connection((host, port), timeout=5) as connection:
            connection.sendall(request)
            reply = b""
            while b"\r\n\r\n" not in reply:
                chunk = connection.recv(8192)
                if not chunk:
                    break
                reply += chunk
            head, _, body = reply.partition(b"\r\n\r\n")
            length = 0
            for line in head.split(b"\r\n"):
                name, _, value = line.partition(b":")
                if name.strip().lower() == b"content-length":
                    length = int(value.strip())
            while len(body) < length:
                chunk = connection.recv(8192)
                if not chunk:
                    break
                body += chunk
            return (head + b"\r\n\r\n" + body).decode("utf-8", errors="replace")

    def test_god_mode_form_mutates_the_world(self):
        before = len(self.engine.creatures)
        data = urllib.parse.urlencode({"share": "0.5"}).encode("utf-8")
        request = urllib.request.Request(self.base + "/god/cull", data=data)
        with urllib.request.urlopen(request, timeout=5):
            pass
        self.assertLess(len(self.engine.creatures), before)


class ServeTests(unittest.TestCase):
    def test_an_impossible_port_raises_a_save_error_asking_for_another(self):
        engine = small_engine(founders=0)
        with self.assertRaises(SaveError) as caught:
            serve(engine, port=70000, out=lambda line: None)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)
        self.assertIn("port", message.lower())

    def test_a_public_bind_warns_that_there_is_no_authentication(self):
        lines = []
        fake_server = mock.Mock()
        fake_server.server_address = ("0.0.0.0", 8000)
        with mock.patch("primordia.web.make_server", return_value=fake_server):
            serve(small_engine(founders=0), host="0.0.0.0", port=8000, out=lines.append)
        warning = "\n".join(lines).lower()
        self.assertIn("authentication", warning)
        fake_server.server_close.assert_called_once()

    def test_a_loopback_bind_stays_quiet(self):
        lines = []
        fake_server = mock.Mock()
        fake_server.server_address = ("127.0.0.1", 8000)
        with mock.patch("primordia.web.make_server", return_value=fake_server):
            serve(small_engine(founders=0), host="127.0.0.1", port=8000, out=lines.append)
        self.assertNotIn("authentication", "\n".join(lines).lower())
