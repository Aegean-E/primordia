"""Unit tests for the engine: determinism, invariants and the behavioural mechanics."""

import time
import unittest

from primordia.engine import Engine
from primordia.genome import GENES, GENE_COUNT, Genome
from primordia.world import WorldConfig


def small_engine(seed: int, founders: int = 30, **overrides) -> Engine:
    config = WorldConfig(width=16, height=10, day_length=60, food_regrowth=0.12, **overrides)
    return Engine(config=config, seed=seed, founders=founders)


def land_tile(engine: Engine) -> tuple[int, int]:
    for y in range(engine.config.height):
        for x in range(engine.config.width):
            if engine.world.is_land(x, y):
                return x, y
    raise AssertionError("the test world holds no land")


def adjacent_land(engine: Engine) -> tuple[tuple[int, int], tuple[int, int]]:
    for y in range(engine.config.height):
        for x in range(engine.config.width - 1):
            if engine.world.is_land(x, y) and engine.world.is_land(x + 1, y):
                return (x, y), (x + 1, y)
    raise AssertionError("the test world holds no adjacent land pair")


def staged_genome(mutability: float = 0.5, **traits: float) -> Genome:
    data = {gene.name: mutability if gene.name == "mutability" else 0.5 for gene in GENES}
    data.update(traits)
    return Genome.from_dict(data)


class DeterminismTests(unittest.TestCase):
    def test_same_seed_replays_the_same_history(self):
        first, second = small_engine(5), small_engine(5)
        for _ in range(60):
            first.step()
            second.step()
        self.assertEqual(first.snapshot_hash(), second.snapshot_hash())
        self.assertEqual(first.tick, second.tick)
        self.assertEqual([c.cid for c in first.creatures], [c.cid for c in second.creatures])

    def test_different_seeds_diverge(self):
        first, second = small_engine(5), small_engine(6)
        for _ in range(40):
            first.step()
            second.step()
        self.assertNotEqual(first.snapshot_hash(), second.snapshot_hash())


class InvariantTests(unittest.TestCase):
    def test_creatures_stay_alive_on_land_within_bounds(self):
        engine = small_engine(11)
        for _ in range(100):
            engine.step()
        self.assertGreaterEqual(len(engine.creatures), 1)
        for creature in engine.creatures:
            self.assertTrue(creature.alive)
            self.assertGreater(creature.energy, 0.0)
            self.assertTrue(0 <= creature.x < engine.config.width)
            self.assertTrue(0 <= creature.y < engine.config.height)
            self.assertTrue(engine.world.is_land(creature.x, creature.y))

    def test_world_layers_stay_in_their_ranges(self):
        engine = small_engine(21)
        for _ in range(80):
            engine.step()
        self.assertLessEqual(max(engine.world.food), engine.world.config.food_cap)
        self.assertGreaterEqual(min(engine.world.food), 0.0)
        self.assertGreaterEqual(min(engine.world.temperature), 0.0)
        self.assertLessEqual(max(engine.world.temperature), 1.0)

    def test_population_dynamics_move_over_time(self):
        engine = small_engine(7)
        before = engine.next_cid
        for _ in range(120):
            engine.step()
        self.assertGreater(engine.next_cid, before)


class ResilienceTests(unittest.TestCase):
    def test_an_empty_world_keeps_ticking_without_incident(self):
        engine = small_engine(4, founders=0)
        for _ in range(50):
            engine.step()
        self.assertEqual(engine.tick, 50)
        self.assertEqual(engine.creatures, [])
        self.assertEqual(len(engine.registry), 0)
        self.assertEqual(len(engine.fossil.events), 0)

    def test_a_dead_world_keeps_ticking_and_records_the_extinction(self):
        engine = small_engine(2, founders=5)
        engine.step()
        for creature in engine.creatures:
            creature.alive = False
        for _ in range(20):
            engine.step()
        self.assertEqual(engine.tick, 21)
        self.assertEqual(engine.creatures, [])
        self.assertGreaterEqual(engine.fossil.extinctions, 1)


class BehaviourTests(unittest.TestCase):
    def test_grazing_moves_energy_from_the_soil_to_the_grazer(self):
        engine = small_engine(2, founders=0, initial_food_share=0.0)
        x, y = land_tile(engine)
        tile = engine.world.index(x, y)
        engine.world.food[tile] = 5.0
        grazer = engine.spawn(
            staged_genome(size=0.2, diet=0.0, curiosity=0.0, social=0.0, speed=0.0),
            x, y, energy=20.0,
        )
        engine.step()
        self.assertLess(engine.world.food[tile], 4.0)
        self.assertGreater(grazer.energy, 20.5)

    def test_grazer_grazes_where_it_stands_instead_of_marching_to_equal_stock(self):
        engine = small_engine(4, founders=0, initial_food_share=0.0)
        (lx, ly), (rx, ry) = adjacent_land(engine)
        own, left = engine.world.index(rx, ry), engine.world.index(lx, ly)
        cap = engine.world.config.food_cap
        engine.world.food[own] = cap
        engine.world.food[left] = cap
        grazer = engine.spawn(
            staged_genome(size=0.2, diet=0.0, curiosity=0.0, social=0.0, speed=0.0),
            rx, ry, energy=20.0,
        )
        engine.step()
        self.assertEqual((grazer.x, grazer.y), (rx, ry))
        self.assertLess(engine.world.food[own], cap)

    def test_attack_kills_a_weaker_neighbour_and_feeds_the_hunter(self):
        engine = small_engine(3, founders=0)
        (hx, hy), (vx, vy) = adjacent_land(engine)
        hunter = engine.spawn(staged_genome(size=0.9, diet=0.9, aggression=0.9), hx, hy, energy=20.0)
        victim = engine.spawn(staged_genome(size=0.3, diet=0.2, aggression=0.1), vx, vy, energy=10.0)
        engine.step()
        self.assertFalse(victim.alive)
        self.assertFalse(any(creature.cid == victim.cid for creature in engine.creatures))
        self.assertGreater(hunter.energy, 21.0)

    def test_armored_victim_takes_less_damage(self):
        engine = small_engine(13, founders=0)
        (hx, hy), (vx, vy) = adjacent_land(engine)
        hunter = engine.spawn(staged_genome(size=0.9, diet=0.9, aggression=0.9), hx, hy, energy=20.0)
        victim = engine.spawn(staged_genome(size=0.8, diet=0.2, aggression=0.1), vx, vy, energy=10.0)
        engine.world.food[engine.world.index(hx, hy)] = 0.0
        engine.world.food[engine.world.index(vx, vy)] = 0.0
        engine.step()
        self.assertTrue(victim.alive)
        self.assertGreater(victim.energy, 3.0)

    def test_two_creatures_reproduce_and_children_hold_bounded_genomes(self):
        engine = small_engine(9, founders=0)
        (x1, y1), (x2, y2) = adjacent_land(engine)
        engine.spawn(staged_genome(size=0.4, fecundity=1.0, diet=0.1), x1, y1, energy=200.0)
        engine.spawn(staged_genome(size=0.4, fecundity=1.0, diet=0.1), x2, y2, energy=200.0)
        for _ in range(200):
            engine.step()
        self.assertGreaterEqual(engine.next_cid, 4)
        self.assertGreater(len(engine.creatures), 2)
        for creature in engine.creatures:
            self.assertEqual(len(creature.genome.genes), GENE_COUNT)


class SpeciesIntegrationTests(unittest.TestCase):
    def test_founders_start_as_one_species(self):
        engine = small_engine(4)
        self.assertEqual(len(engine.registry), 1)
        self.assertTrue(all(creature.species == 1 for creature in engine.creatures))

    def test_census_populates_the_fossil_record(self):
        engine = small_engine(4)
        for _ in range(20):
            engine.step()
        trace = engine.fossil.traces[1]
        self.assertEqual(trace.first_seen, 0)
        self.assertGreaterEqual(trace.peak_population, 1)
        self.assertGreaterEqual(trace.last_seen, 1)

    def test_drift_grows_the_registry_over_time(self):
        engine = small_engine(4)
        for _ in range(400):
            engine.step()
        self.assertGreaterEqual(len(engine.registry), 2)
        self.assertGreaterEqual(engine.fossil.speciations, 1)


class PerformanceTests(unittest.TestCase):
    def test_a_short_default_run_stays_fast(self):
        engine = Engine(config=WorldConfig(), seed=1, founders=120)
        start = time.perf_counter()
        for _ in range(120):
            engine.step()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 8.0)
