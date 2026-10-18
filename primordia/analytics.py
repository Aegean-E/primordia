"""Small pure statistics over a population: counts by species and mean gene values."""

from __future__ import annotations

from typing import Dict, Sequence

from primordia.creature import Creature
from primordia.genome import GENES


def species_counts(creatures: Sequence[Creature]) -> Dict[int, int]:
    """How many living creatures belong to each species id."""
    counts: Dict[int, int] = {}
    for creature in creatures:
        counts[creature.species] = counts.get(creature.species, 0) + 1
    return counts


def trait_means(creatures: Sequence[Creature]) -> Dict[str, float]:
    """The population's mean value per gene; all zeros for an empty population."""
    if not creatures:
        return {gene.name: 0.0 for gene in GENES}
    total = len(creatures)
    return {gene.name: sum(creature.genome.trait(gene.name) for creature in creatures) / total
            for gene in GENES}
