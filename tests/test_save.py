"""Unit tests for persistence: exact round trips, atomic writes, backup fallback and quarantine."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from primordia import shocks
from primordia.engine import Engine
from primordia.genome import GENES, Genome
from primordia.save import SAVE_VERSION, SaveError, load_from, save_to
from primordia.species import SPECIATION_DISTANCE, SpeciesRegistry
from primordia.world import WorldConfig


def small_config(**overrides) -> WorldConfig:
    """A fast test world; the overrides let a test pin what it stages."""
    base = dict(width=16, height=10, day_length=60, food_regrowth=0.12)
    base.update(overrides)
    return WorldConfig(**base)


def flat_genome() -> Genome:
    return Genome(genes=tuple(0.5 for _ in GENES))


def land_tile(engine: Engine) -> tuple[int, int]:
    for y in range(engine.config.height):
        for x in range(engine.config.width):
            if engine.world.is_land(x, y):
                return x, y
    raise AssertionError("the test world holds no land")


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run.json"

    def test_resumed_run_replays_the_same_history(self):
        original = Engine(config=small_config(), seed=3, founders=30)
        for _ in range(60):
            original.step()
        save_to(original, self.path)
        resumed = load_from(self.path)
        self.assertEqual(resumed.snapshot_hash(), original.snapshot_hash())
        self.assertEqual(resumed.tick, original.tick)
        for _ in range(60):
            resumed.step()
            original.step()
        self.assertEqual(resumed.snapshot_hash(), original.snapshot_hash())
        self.assertEqual([c.cid for c in resumed.creatures], [c.cid for c in original.creatures])

    def test_species_registry_and_fossil_record_survive_the_round_trip(self):
        original = Engine(config=small_config(), seed=4, founders=30)
        for _ in range(150):
            original.step()
        self.assertGreaterEqual(len(original.registry), 2)
        save_to(original, self.path)
        resumed = load_from(self.path)
        self.assertEqual(len(resumed.registry), len(original.registry))
        for species_id in range(1, len(original.registry) + 1):
            before = original.registry.get(species_id)
            after = resumed.registry.get(species_id)
            self.assertEqual(after.ancestor, before.ancestor)
            self.assertEqual(after.birth_tick, before.birth_tick)
            self.assertEqual(after.founder_genome, before.founder_genome)
        self.assertEqual(resumed.fossil.speciations, original.fossil.speciations)
        self.assertEqual(resumed.fossil.extinctions, original.fossil.extinctions)
        self.assertEqual(sorted(resumed.fossil.traces), sorted(original.fossil.traces))
        self.assertEqual([c.species for c in resumed.creatures],
                         [c.species for c in original.creatures])

    def test_an_integer_energy_keeps_the_hash_across_the_round_trip(self):
        original = Engine(config=small_config(), seed=7, founders=0)
        x, y = land_tile(original)
        original.spawn(flat_genome(), x, y, energy=45)
        save_to(original, self.path)
        resumed = load_from(self.path)
        self.assertEqual(resumed.snapshot_hash(), original.snapshot_hash())

    def test_a_custom_species_threshold_survives_the_round_trip(self):
        original = Engine(config=small_config(), seed=7, founders=0)
        original.registry = SpeciesRegistry(distance=0.30)
        x, y = land_tile(original)
        original.spawn(flat_genome(), x, y, energy=20.0)
        save_to(original, self.path)
        resumed = load_from(self.path)
        self.assertEqual(resumed.registry.distance, 0.30)
        self.assertEqual(resumed.snapshot_hash(), original.snapshot_hash())

    def test_a_save_without_a_species_threshold_uses_the_default(self):
        engine = Engine(config=small_config(), seed=7, founders=5)
        save_to(engine, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        del data["species_distance"]
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(load_from(self.path).registry.distance, SPECIATION_DISTANCE)

    def test_save_carries_the_format_version(self):
        engine = Engine(config=small_config(), seed=5, founders=10)
        save_to(engine, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], SAVE_VERSION)

    def test_a_newer_save_version_is_refused_without_quarantine(self):
        engine = Engine(config=small_config(), seed=5, founders=10)
        save_to(engine, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["version"] = SAVE_VERSION + 1
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(SaveError) as caught:
            load_from(self.path)
        self.assertIn("version", str(caught.exception))
        self.assertTrue(self.path.exists())
        self.assertEqual(list(self.path.parent.glob(self.path.name + ".corrupt_*")), [])

    def test_a_json_file_without_a_version_is_not_taken_for_a_save(self):
        self.path.write_text(json.dumps({"hello": "there"}), encoding="utf-8")
        with self.assertRaises(SaveError) as caught:
            load_from(self.path)
        self.assertIn("not a primordia save", str(caught.exception))
        self.assertTrue(self.path.exists())

    def test_a_shocked_world_round_trips_exactly(self):
        original = Engine(config=small_config(), seed=4, founders=30)
        for _ in range(60):
            original.step()
        shocks.meteor(original, 8, 5, radius=2)
        shocks.bloom(original, 4, 4, radius=2, share=0.5)
        shocks.cull(original, 0.25)
        shocks.introduce(original, 4)
        save_to(original, self.path)
        resumed = load_from(self.path)
        for _ in range(60):
            resumed.step()
            original.step()
        self.assertEqual(resumed.snapshot_hash(), original.snapshot_hash())


class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run.json"

    def saved_data(self) -> dict:
        engine = Engine(config=small_config(), seed=3, founders=10)
        save_to(engine, self.path)
        return json.loads(self.path.read_text(encoding="utf-8"))

    def load_tampered(self, data: dict):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return load_from(self.path)

    def assert_refused(self, data: dict) -> str:
        with self.assertRaises(SaveError) as caught:
            self.load_tampered(data)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)
        return message

    def test_a_short_terrain_layer_is_refused_before_the_tick_loop(self):
        data = self.saved_data()
        data["world"]["terrain"] = data["world"]["terrain"][:3]
        self.assert_refused(data)

    def test_a_short_food_layer_is_refused(self):
        data = self.saved_data()
        data["world"]["food"] = data["world"]["food"][:1]
        self.assert_refused(data)

    def test_an_out_of_bounds_creature_is_refused(self):
        data = self.saved_data()
        data["creatures"][0]["x"] = data["config"]["width"] + 5
        self.assert_refused(data)

    def test_a_creature_with_an_unknown_species_is_refused(self):
        data = self.saved_data()
        data["creatures"][0]["species"] = 99
        self.assert_refused(data)

    def test_a_creature_with_non_finite_energy_is_refused(self):
        data = self.saved_data()
        data["creatures"][0]["energy"] = float("nan")
        self.assert_refused(data)

    def test_a_missing_species_record_is_refused(self):
        data = self.saved_data()
        data["species"] = []
        self.assert_refused(data)

    def test_an_age_outside_the_run_is_refused(self):
        for age in (-1, 10 ** 6):
            with self.subTest(age=age):
                data = self.saved_data()
                data["creatures"][0]["age"] = age
                self.assert_refused(data)

    def test_impossible_fossil_dates_are_refused(self):
        def stamped_data() -> dict:
            engine = Engine(config=small_config(), seed=3, founders=10)
            for _ in range(20):
                engine.step()
            engine.fossil.record_speciation(tick=engine.tick, species_id=1, ancestor=0,
                                            detail="probe")
            save_to(engine, self.path)
            return json.loads(self.path.read_text(encoding="utf-8"))

        def trace(data: dict) -> dict:
            return data["fossil"]["traces"][str(next(iter(data["fossil"]["traces"])))]

        cases = {
            "first after last": lambda data: trace(data).update(
                {"first_seen": data["tick"], "last_seen": 0}),
            "future sighting": lambda data: trace(data).update(
                {"last_seen": data["tick"] + 1}),
            "future extinction": lambda data: trace(data).__setitem__(
                "extinct_tick", data["tick"] + 1),
            "future event": lambda data: data["fossil"]["events"][0].__setitem__(
                "tick", data["tick"] + 1),
            "impossible ancestor": lambda data: data["fossil"]["events"][0].__setitem__(
                "ancestor", 99),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                data = stamped_data()
                mutate(data)
                self.assert_refused(data)

    def test_duplicate_creature_ids_are_refused(self):
        data = self.saved_data()
        data["creatures"][1]["cid"] = data["creatures"][0]["cid"]
        self.assert_refused(data)

    def test_saving_non_finite_state_is_a_save_error(self):
        engine = Engine(config=small_config(), seed=3, founders=10)
        engine.creatures[0].energy = float("nan")
        with self.assertRaises(SaveError) as caught:
            save_to(engine, self.path)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)
        self.assertEqual(list(self.path.parent.glob("*.tmp_*")), [])

    def test_a_directory_backup_is_unusable_instead_of_a_raw_oserror(self):
        self.saved_data()
        self.path.write_text("{broken", encoding="utf-8")
        Path(str(self.path) + ".bak").mkdir()
        with self.assertRaises(SaveError) as caught:
            load_from(self.path)
        self.assertIn("Why:", str(caught.exception))
        self.assertIn("Fix:", str(caught.exception))


class AtomicityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run.json"
        self.backup = Path(str(self.path) + ".bak")

    def test_overwriting_keeps_the_previous_save_as_a_backup(self):
        first = Engine(config=small_config(), seed=3, founders=10)
        save_to(first, self.path)
        second = Engine(config=small_config(), seed=9, founders=10)
        for _ in range(30):
            second.step()
        save_to(second, self.path)
        self.assertTrue(self.backup.exists())
        self.assertEqual(load_from(self.path).snapshot_hash(), second.snapshot_hash())
        self.assertEqual(load_from(self.backup).snapshot_hash(), first.snapshot_hash())

    def test_a_corrupt_save_falls_back_to_the_backup_and_quarantines_the_wreck(self):
        first = Engine(config=small_config(), seed=3, founders=10)
        save_to(first, self.path)
        second = Engine(config=small_config(), seed=9, founders=10)
        for _ in range(30):
            second.step()
        save_to(second, self.path)
        self.path.write_text("not json at all", encoding="utf-8")
        recovered = load_from(self.path)
        self.assertEqual(recovered.snapshot_hash(), first.snapshot_hash())
        wreckage = list(self.path.parent.glob(self.path.name + ".corrupt_*"))
        self.assertEqual(len(wreckage), 1)
        self.assertEqual(load_from(self.path).snapshot_hash(), first.snapshot_hash())

    def test_double_corruption_raises_with_why_and_fix(self):
        engine = Engine(config=small_config(), seed=3, founders=10)
        save_to(engine, self.path)
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(SaveError) as caught:
            load_from(self.path)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)

    def test_missing_file_raises_with_guidance(self):
        with self.assertRaises(SaveError) as caught:
            load_from(self.path)
        self.assertIn("Why:", str(caught.exception))
        self.assertIn("Fix:", str(caught.exception))

    def test_a_missing_primary_with_a_live_backup_restores_itself(self):
        first = Engine(config=small_config(), seed=3, founders=10)
        save_to(first, self.path)
        second = Engine(config=small_config(), seed=9, founders=10)
        for _ in range(30):
            second.step()
        save_to(second, self.path)
        self.path.unlink()
        restored = load_from(self.path)
        self.assertEqual(restored.snapshot_hash(), first.snapshot_hash())
        self.assertTrue(self.path.exists())
        self.assertEqual(load_from(self.path).snapshot_hash(), first.snapshot_hash())

    def test_a_failed_replace_leaves_no_temp_file(self):
        engine = Engine(config=small_config(), seed=3, founders=10)
        with mock.patch("primordia.save._replace", side_effect=OSError("busy")):
            with self.assertRaises(SaveError):
                save_to(engine, self.path)
        self.assertEqual(list(self.path.parent.glob("*.tmp_*")), [])

    def test_reading_a_folder_raises_a_save_error_not_a_crash(self):
        folder = Path(self.temp.name) / "run.json"
        folder.mkdir()
        with self.assertRaises(SaveError) as caught:
            load_from(folder)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)
        self.assertTrue(folder.is_dir())

    def test_writing_onto_a_folder_is_refused_before_anything_moves(self):
        folder = Path(self.temp.name) / "run.json"
        folder.mkdir()
        engine = Engine(config=small_config(), seed=3, founders=10)
        with self.assertRaises(SaveError) as caught:
            save_to(engine, folder)
        self.assertIn("Fix:", str(caught.exception))
        self.assertTrue(folder.is_dir())
        self.assertEqual(list(folder.iterdir()), [])
        self.assertFalse(self.backup.exists())

    def test_a_quarantine_that_cannot_move_the_file_raises_cleanly(self):
        engine = Engine(config=small_config(), seed=3, founders=10)
        save_to(engine, self.path)
        self.path.write_text("{broken", encoding="utf-8")
        with mock.patch("primordia.save.os.replace", side_effect=OSError("locked")):
            with self.assertRaises(SaveError) as caught:
                load_from(self.path)
        message = str(caught.exception)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)
        self.assertTrue(self.path.exists())
