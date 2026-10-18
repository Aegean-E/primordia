"""Unit tests for persistence: exact round trips, atomic writes, backup fallback and quarantine."""

import json
import tempfile
import unittest
from pathlib import Path

from primordia import shocks
from primordia.engine import Engine
from primordia.save import SAVE_VERSION, SaveError, load_from, save_to
from primordia.world import WorldConfig


def small_config(**overrides) -> WorldConfig:
    """A fast test world; the overrides let a test pin what it stages."""
    base = dict(width=16, height=10, day_length=60, food_regrowth=0.12)
    base.update(overrides)
    return WorldConfig(**base)


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

    def test_save_carries_the_format_version(self):
        engine = Engine(config=small_config(), seed=5, founders=10)
        save_to(engine, self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], SAVE_VERSION)

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
