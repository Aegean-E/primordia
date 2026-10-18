"""Unit tests for the species registry: phenetic clustering around founding genomes."""

import unittest

from primordia.genome import GENES, Genome
from primordia.species import SpeciesRegistry


def centered(**traits: float) -> Genome:
    data = {gene.name: 0.5 for gene in GENES}
    data.update(traits)
    return Genome.from_dict(data)


class RegistryTests(unittest.TestCase):
    def test_first_genome_founds_species_one(self):
        registry = SpeciesRegistry()
        species_id, is_new = registry.classify(centered(), tick=0)
        self.assertEqual((species_id, is_new), (1, True))
        self.assertEqual(len(registry), 1)

    def test_near_clones_join_the_same_species(self):
        registry = SpeciesRegistry()
        registry.classify(centered(), tick=0)
        species_id, is_new = registry.classify(centered(speed=0.6), tick=5)
        self.assertEqual((species_id, is_new), (1, False))

    def test_far_drift_founds_a_new_species_with_its_ancestor(self):
        registry = SpeciesRegistry()
        registry.classify(centered(), tick=0)
        far = Genome(genes=tuple(0.8 for _ in GENES))
        species_id, is_new = registry.classify(far, tick=7, ancestor=1)
        self.assertEqual((species_id, is_new), (2, True))
        self.assertEqual(registry.get(2).ancestor, 1)
        self.assertEqual(registry.get(2).birth_tick, 7)

    def test_representative_is_the_founding_genome(self):
        registry = SpeciesRegistry()
        founder = centered()
        registry.classify(founder, tick=0)
        registry.classify(centered(speed=0.6), tick=1)
        self.assertEqual(registry.get(1).founder_genome, founder)

    def test_ids_are_monotonic_and_unique(self):
        registry = SpeciesRegistry()
        self.assertEqual(registry.classify(Genome(genes=tuple(0.0 for _ in GENES)), tick=0)[0], 1)
        self.assertEqual(registry.classify(Genome(genes=tuple(1.0 for _ in GENES)), tick=0)[0], 2)
        self.assertEqual(registry.classify(centered(), tick=0)[0], 3)
        self.assertEqual(len(registry), 3)
