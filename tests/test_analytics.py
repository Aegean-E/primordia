"""Unit tests for the population statistics helpers."""

import unittest

from primordia.analytics import species_counts, trait_means
from primordia.engine import Engine
from primordia.genome import GENES
from primordia.world import WorldConfig


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
