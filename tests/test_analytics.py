"""Unit tests for the population statistics helpers."""

import unittest

from primordia.analytics import species_counts, species_metrics, trait_means
from primordia.engine import Engine
from primordia.genome import GENES, Genome
from primordia.species import SPECIATION_DISTANCE
from primordia.world import WorldConfig


def flat_genome(value: float = 0.5) -> Genome:
    return Genome(genes=tuple(value for _ in GENES))


def diet_genome(diet: float) -> Genome:
    return Genome(genes=tuple(diet if gene.name == "diet" else 0.5 for gene in GENES))


def land_tiles(engine: Engine, count: int):
    tiles = [(x, y) for y in range(engine.config.height)
             for x in range(engine.config.width) if engine.world.is_land(x, y)]
    return tiles[:count]


class AnalyticsTests(unittest.TestCase):
    def test_counts_and_means_on_a_seeded_population(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=4)
        counts = species_counts(engine.creatures)
        self.assertEqual(sum(counts.values()), 4)
        means = trait_means(engine.creatures)
        self.assertEqual(sorted(means), sorted(gene.name for gene in GENES))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in means.values()))

    def test_empty_population_has_no_counts_and_zero_means(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=0)
        self.assertEqual(species_counts(engine.creatures), {})
        self.assertTrue(all(value == 0.0 for value in trait_means(engine.creatures).values()))

    def test_dead_creatures_are_not_counted_or_measured(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=4)
        dead = engine.creatures[0]
        dead.alive = False
        self.assertEqual(sum(species_counts(engine.creatures).values()), 3)
        living_mean = sum(creature.genome.trait("size") for creature in engine.creatures[1:]) / 3
        self.assertAlmostEqual(trait_means(engine.creatures)["size"], living_mean)


class SpeciesMetricsTests(unittest.TestCase):
    def test_metrics_mirror_the_living_counts_and_stay_inside_the_threshold(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=4)
        counts = species_counts(engine.creatures)
        metrics = species_metrics(engine.creatures, engine.registry)
        self.assertEqual(set(metrics), set(counts))
        for species_id, row in metrics.items():
            self.assertEqual(row.species_id, species_id)
            self.assertEqual(row.alive, counts[species_id])
            self.assertGreaterEqual(row.mean_drift, 0.0)
            self.assertLessEqual(row.max_drift, SPECIATION_DISTANCE)
            self.assertLessEqual(row.mean_drift, row.max_drift)
            self.assertLessEqual(row.near_speciation, row.alive)

    def test_an_empty_population_has_no_metrics(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=0)
        self.assertEqual(species_metrics(engine.creatures, engine.registry), {})

    def test_diet_split_and_mean_age_describe_one_lineage(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=0)
        (x1, y1), (x2, y2) = land_tiles(engine, 2)
        grazer = engine.spawn(diet_genome(0.4), x1, y1)
        hunter = engine.spawn(diet_genome(0.6), x2, y2)
        grazer.age, hunter.age = 4, 8
        row = species_metrics(engine.creatures, engine.registry)[grazer.species]
        self.assertEqual(row.herbivores, 1)
        self.assertEqual(row.carnivores, 1)
        self.assertAlmostEqual(row.mean_age, 6.0)

    def test_near_speciation_counts_creatures_close_to_the_threshold(self):
        engine = Engine(config=WorldConfig(width=8, height=5), seed=0, founders=0)
        (x1, y1), (x2, y2), (x3, y3) = land_tiles(engine, 3)
        engine.spawn(flat_genome(0.5), x1, y1)
        engine.spawn(flat_genome(0.65), x2, y2)
        engine.spawn(flat_genome(0.55), x3, y3)
        row = species_metrics(engine.creatures, engine.registry)[1]
        self.assertEqual(row.alive, 3)
        self.assertEqual(row.near_speciation, 1)
        self.assertAlmostEqual(row.max_drift, 0.15)
        self.assertAlmostEqual(row.mean_drift, (0.0 + 0.15 + 0.05) / 3)
