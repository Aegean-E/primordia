"""Unit tests for the world: terrain, the food layer and the temperature field."""

import random
import unittest

from primordia.world import LAND, WATER, World, WorldConfig


def make_world(seed: int = 0, **overrides) -> World:
    config = WorldConfig(**overrides) if overrides else WorldConfig()
    return World(config, random.Random(seed))


class TerrainTests(unittest.TestCase):
    def test_terrain_is_binary_and_holds_land(self):
        for seed in range(10):
            world = make_world(seed)
            self.assertTrue(set(world.terrain) <= {LAND, WATER})
            self.assertIn(LAND, world.terrain)

    def test_index_and_xy_round_trip(self):
        world = make_world(1, width=7, height=5)
        for y in range(5):
            for x in range(7):
                self.assertEqual(world.xy(world.index(x, y)), (x, y))

    def test_generation_is_seeded_reproducible(self):
        first, second = make_world(3), make_world(3)
        self.assertEqual(first.terrain, second.terrain)
        self.assertEqual(first.phase, second.phase)


class FoodTests(unittest.TestCase):
    def test_food_regrows_but_never_exceeds_the_cap(self):
        world = make_world(0, width=8, height=4, food_cap=5.0, food_regrowth=0.5)
        for tick in range(40):
            world.update(tick)
        land = [value for value, tile in zip(world.food, world.terrain) if tile == LAND]
        self.assertTrue(land)
        self.assertGreater(max(land), 0.0)
        self.assertLessEqual(max(land), 5.0)

    def test_water_tiles_are_barren(self):
        world = make_world(8, width=4, height=2, water_ratio=1.0)
        for tick in range(5):
            world.update(tick)
        for tile in range(world.length):
            self.assertEqual(world.food[tile], 0.0)
            self.assertEqual(world.take_food(tile, 1.0), 0.0)

    def test_take_food_is_bounded_and_leaves_no_debt(self):
        world = make_world(4, width=6, height=3)
        tile = world.terrain.index(LAND)
        world.update(0)
        taken = world.take_food(tile, 10_000.0)
        self.assertGreaterEqual(taken, 0.0)
        self.assertGreaterEqual(world.food[tile], 0.0)
        self.assertLessEqual(taken, world.config.food_cap)

    def test_add_food_returns_a_carcass_to_the_soil(self):
        world = make_world(5, width=6, height=3, food_cap=3.0)
        tile = world.terrain.index(LAND)
        world.add_food(tile, 2.0)
        self.assertAlmostEqual(world.food[tile], 2.0)
        world.add_food(tile, 99.0)
        self.assertAlmostEqual(world.food[tile], 3.0)


class TemperatureTests(unittest.TestCase):
    def test_temperature_stays_in_the_unit_interval(self):
        world = make_world(6, day_length=25)
        for tick in range(60):
            world.update(tick)
            self.assertGreaterEqual(min(world.temperature), 0.0)
            self.assertLessEqual(max(world.temperature), 1.0)

    def test_temperature_advances_seasonally(self):
        world = make_world(7, day_length=25)
        samples = []
        for tick in range(50):
            world.update(tick)
            samples.append(world.temperature[world.index(1, 1)])
        self.assertGreater(max(samples) - min(samples), 0.1)

    def test_food_growth_follows_the_season(self):
        world = make_world(9, width=2, height=2, day_length=40, food_cap=100.0,
                           food_regrowth=1.0, water_ratio=0.0)
        tile = world.index(0, 0)
        growth = []
        for tick in range(40):
            before = world.food[tile]
            world.update(tick)
            growth.append(world.food[tile] - before)
        self.assertGreater(max(growth), 2.0 * min(growth))
