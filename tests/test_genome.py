"""Unit tests for the genome model: bounds, determinism and the variation operators."""

import random
import unittest
from dataclasses import FrozenInstanceError

from primordia.genome import (
    GENE_COUNT,
    GENE_INDEX,
    GENES,
    Genome,
    crossover,
    genetic_distance,
    mutate,
    random_genome,
)


def genome_with(mutability: float) -> Genome:
    """A genome centered at 0.5 with one chosen mutability gene."""
    return Genome(genes=tuple(mutability if gene.name == "mutability" else 0.5 for gene in GENES))


class GeneCatalogTests(unittest.TestCase):
    def test_names_are_unique_and_indexes_match(self):
        names = [gene.name for gene in GENES]
        self.assertEqual(len(names), GENE_COUNT)
        self.assertEqual(len(set(names)), GENE_COUNT)
        for index, gene in enumerate(GENES):
            self.assertEqual(GENE_INDEX[gene.name], index)
            self.assertLess(gene.low, gene.high)
            self.assertTrue(gene.description)


class GenomeModelTests(unittest.TestCase):
    def test_random_genome_is_full_length_and_bounded(self):
        for seed in range(50):
            genome = random_genome(random.Random(seed))
            self.assertEqual(len(genome.genes), GENE_COUNT)
            for gene, value in zip(GENES, genome.genes):
                self.assertGreaterEqual(value, gene.low, gene.name)
                self.assertLessEqual(value, gene.high, gene.name)

    def test_random_genome_is_seeded_reproducible(self):
        first = random_genome(random.Random(7))
        second = random_genome(random.Random(7))
        self.assertEqual(first.genes, second.genes)

    def test_genome_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            Genome(genes=tuple(0.5 for _ in range(GENE_COUNT - 1)))

    def test_genome_rejects_out_of_range_gene(self):
        genes = [0.5] * GENE_COUNT
        genes[GENE_INDEX["speed"]] = 1.5
        with self.assertRaises(ValueError):
            Genome(genes=tuple(genes))

    def test_genome_is_immutable(self):
        genome = random_genome(random.Random(1))
        with self.assertRaises(FrozenInstanceError):
            genome.genes = ()

    def test_trait_reads_by_name(self):
        genome = random_genome(random.Random(4))
        self.assertEqual(genome.trait("speed"), genome.genes[GENE_INDEX["speed"]])

    def test_as_dict_and_from_dict_round_trip(self):
        genome = random_genome(random.Random(3))
        self.assertEqual(Genome.from_dict(genome.as_dict()).genes, genome.genes)
        self.assertEqual(sorted(genome.as_dict()), sorted(gene.name for gene in GENES))

    def test_from_dict_requires_every_gene(self):
        data = random_genome(random.Random(5)).as_dict()
        data.pop("sense")
        with self.assertRaises(KeyError):
            Genome.from_dict(data)


class MutationTests(unittest.TestCase):
    def test_mutation_never_leaves_bounds(self):
        rng = random.Random(11)
        genome = Genome(genes=tuple(0.0 for _ in range(GENE_COUNT)))
        for _ in range(200):
            genome = mutate(genome, rng)
            for value in genome.genes:
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_mutation_is_seeded_reproducible(self):
        base = random_genome(random.Random(2))
        self.assertEqual(mutate(base, random.Random(9)).genes, mutate(base, random.Random(9)).genes)

    def test_mutation_changes_genes_over_time(self):
        rng = random.Random(12)
        base = Genome(genes=tuple(0.5 for _ in range(GENE_COUNT)))
        mutants = [mutate(base, rng) for _ in range(30)]
        self.assertTrue(any(mutant.genes != base.genes for mutant in mutants))

    def test_mutability_gene_scales_the_step(self):
        quiet = sum(self._drift(genome_with(0.0), seed) for seed in range(300))
        noisy = sum(self._drift(genome_with(1.0), seed) for seed in range(300))
        self.assertGreater(noisy, quiet)

    @staticmethod
    def _drift(genome: Genome, seed: int) -> float:
        mutant = mutate(genome, random.Random(seed))
        return sum(abs(before - after) for before, after in zip(genome.genes, mutant.genes))


class CrossoverTests(unittest.TestCase):
    def test_child_genes_come_whole_from_either_parent(self):
        low = Genome(genes=tuple(0.0 for _ in range(GENE_COUNT)))
        high = Genome(genes=tuple(1.0 for _ in range(GENE_COUNT)))
        child = crossover(low, high, random.Random(5))
        self.assertTrue(all(value in (0.0, 1.0) for value in child.genes))

    def test_crossover_mixes_both_parents_across_seeds(self):
        low = Genome(genes=tuple(0.0 for _ in range(GENE_COUNT)))
        high = Genome(genes=tuple(1.0 for _ in range(GENE_COUNT)))
        children = [crossover(low, high, random.Random(seed)) for seed in range(40)]
        self.assertTrue(any(0.0 in child.genes and 1.0 in child.genes for child in children))

    def test_crossover_is_seeded_reproducible(self):
        first = random_genome(random.Random(1))
        second = random_genome(random.Random(2))
        self.assertEqual(
            crossover(first, second, random.Random(6)).genes,
            crossover(first, second, random.Random(6)).genes,
        )


class DistanceTests(unittest.TestCase):
    def test_distance_is_zero_symmetric_and_bounded(self):
        low = Genome(genes=tuple(0.0 for _ in range(GENE_COUNT)))
        high = Genome(genes=tuple(1.0 for _ in range(GENE_COUNT)))
        self.assertEqual(genetic_distance(low, low), 0.0)
        self.assertEqual(genetic_distance(low, high), 1.0)
        self.assertEqual(genetic_distance(low, high), genetic_distance(high, low))
        rng = random.Random(8)
        first, second = random_genome(rng), random_genome(rng)
        self.assertGreaterEqual(genetic_distance(first, second), 0.0)
        self.assertLessEqual(genetic_distance(first, second), 1.0)
