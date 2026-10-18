"""Primordia genomes: a fixed vector of bounded genes and the operators that vary them.

A genome is `GENE_COUNT` genes, each normalized to [0, 1]; the engine decodes them into
physical traits (speed, metabolism, diet...). `mutate` scales its step by the genome's own
`mutability` gene, so evolvability itself evolves. Every operator draws from an injected
`random.Random`, so one seed reproduces a run exactly and the tests can replay any history.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

GENOME_VERSION = 1
GENE_MIN = 0.0
GENE_MAX = 1.0
# Chance that one gene mutates per `mutate` call, and the bounded step it may then take.
MUTATION_CHANCE_PER_GENE = 0.15
MUTATION_BASE_STEP = 0.10
MUTATION_STEP_GAIN = 0.40
MUTABILITY_GENE = "mutability"


@dataclass(frozen=True)
class GeneSpec:
    """One gene: the normalized range it lives in and what the engine decodes it to."""

    name: str
    low: float
    high: float
    description: str


GENES: Tuple[GeneSpec, ...] = (
    GeneSpec("size", GENE_MIN, GENE_MAX, "body size: more energy capacity and defense, higher upkeep"),
    GeneSpec("speed", GENE_MIN, GENE_MAX, "tiles moved per tick, paid for in energy"),
    GeneSpec("metabolism", GENE_MIN, GENE_MAX, "metabolic efficiency: slow burn versus fast burn"),
    GeneSpec("diet", GENE_MIN, GENE_MAX, "foraging mode: 0 grazes plants, 1 hunts other creatures"),
    GeneSpec("sense", GENE_MIN, GENE_MAX, "perception radius for food, threats and mates"),
    GeneSpec("aggression", GENE_MIN, GENE_MAX, "readiness to attack rather than avoid a neighbor"),
    GeneSpec("social", GENE_MIN, GENE_MAX, "attraction to kin and crowds versus solitude"),
    GeneSpec("fecundity", GENE_MIN, GENE_MAX, "offspring per successful reproduction"),
    GeneSpec("lifespan", GENE_MIN, GENE_MAX, "resistance to aging and starvation damage"),
    GeneSpec("thermophily", GENE_MIN, GENE_MAX, "preferred temperature band of the world"),
    GeneSpec("curiosity", GENE_MIN, GENE_MAX, "wandering drive versus staying put in plenty"),
    GeneSpec("mutability", GENE_MIN, GENE_MAX, "own mutation rate: how far its children may stray"),
)

GENE_INDEX: Dict[str, int] = {gene.name: index for index, gene in enumerate(GENES)}
GENE_COUNT = len(GENES)


@dataclass(frozen=True)
class Genome:
    """An immutable gene vector; every gene lies inside its `GeneSpec` range."""

    genes: Tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.genes) != GENE_COUNT:
            raise ValueError(
                f"a genome holds {GENE_COUNT} genes, got {len(self.genes)}; "
                f"build one with random_genome(), crossover() or Genome.from_dict()"
            )
        for spec, value in zip(GENES, self.genes):
            if not spec.low <= value <= spec.high:
                raise ValueError(
                    f"gene '{spec.name}' is {value}, outside [{spec.low}, {spec.high}]; "
                    f"the variation operators clamp before constructing a Genome"
                )

    def trait(self, name: str) -> float:
        """The value of gene `name`, so readers decode by meaning rather than by index."""
        return self.genes[GENE_INDEX[name]]

    def as_dict(self) -> Dict[str, float]:
        """The genome as a name-to-value mapping, the shape the save format and web UI read."""
        return {spec.name: value for spec, value in zip(GENES, self.genes)}

    @classmethod
    def from_dict(cls, data: Mapping[str, float]) -> "Genome":
        """Rebuild a genome from `as_dict` output; a missing gene raises KeyError."""
        return cls(genes=tuple(float(data[spec.name]) for spec in GENES))


def random_genome(rng: random.Random) -> Genome:
    """A fresh genome with every gene drawn uniformly from its range."""
    return Genome(genes=tuple(rng.uniform(spec.low, spec.high) for spec in GENES))


def mutate(genome: Genome, rng: random.Random) -> Genome:
    """A child genome: each gene mutates with `MUTATION_CHANCE_PER_GENE`, then clamps."""
    step = MUTATION_BASE_STEP + MUTATION_STEP_GAIN * genome.trait(MUTABILITY_GENE)
    genes = list(genome.genes)
    for index, spec in enumerate(GENES):
        if rng.random() < MUTATION_CHANCE_PER_GENE:
            delta = rng.uniform(-step, step)
            genes[index] = min(spec.high, max(spec.low, genes[index] + delta))
    return Genome(genes=tuple(genes))


def crossover(parent_a: Genome, parent_b: Genome, rng: random.Random) -> Genome:
    """A child genome assembled from whole genes of either parent, a coin flip per gene."""
    genes = tuple(a if rng.random() < 0.5 else b for a, b in zip(parent_a.genes, parent_b.genes))
    return Genome(genes=genes)


def genetic_distance(a: Genome, b: Genome) -> float:
    """Root-mean-square gene difference in [0, 1]; species clustering reads this."""
    squared = sum((x - y) ** 2 for x, y in zip(a.genes, b.genes))
    return math.sqrt(squared / GENE_COUNT)
