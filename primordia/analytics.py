"""Small pure statistics over a population: counts by species, mean gene values and drift.

Drift is how far a living lineage has strayed from its founding genome, measured by the same
`genetic_distance` the species registry clusters with. A creature near the speciation threshold
is a lineage about to split; the observatory and the command line report that share directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from primordia.creature import Creature
from primordia.genome import GENES, genetic_distance
from primordia.species import SpeciesRegistry

NEAR_SPECIATION_FRACTION = 0.8
DIET_SPLIT = 0.5


def species_counts(creatures: Sequence[Creature]) -> Dict[int, int]:
    """How many living creatures belong to each species id."""
    counts: Dict[int, int] = {}
    for creature in creatures:
        if creature.alive:
            counts[creature.species] = counts.get(creature.species, 0) + 1
    return counts


def trait_means(creatures: Sequence[Creature]) -> Dict[str, float]:
    """The living population's mean value per gene; all zeros for an empty population."""
    living = [creature for creature in creatures if creature.alive]
    if not living:
        return {gene.name: 0.0 for gene in GENES}
    total = len(living)
    return {gene.name: sum(creature.genome.trait(gene.name) for creature in living) / total
            for gene in GENES}


@dataclass(frozen=True)
class SpeciesMetrics:
    """One living lineage's spread: drift from its founder, and who is in it."""

    species_id: int
    alive: int
    mean_drift: float
    max_drift: float
    near_speciation: int
    herbivores: int
    carnivores: int
    mean_age: float


def species_metrics(creatures: Sequence[Creature],
                    registry: SpeciesRegistry) -> Dict[int, SpeciesMetrics]:
    """Per living species: drift from its founding genome and its living composition.

    Drift is the raw `genetic_distance` to the species' founder, so compare it with
    `registry.distance` to read how close the lineage is to a split.
    """
    members: Dict[int, List[Creature]] = {}
    for creature in creatures:
        if creature.alive:
            members.setdefault(creature.species, []).append(creature)
    metrics: Dict[int, SpeciesMetrics] = {}
    near_threshold = registry.distance * NEAR_SPECIATION_FRACTION
    for species_id, group in members.items():
        founder = registry.get(species_id).founder_genome
        drifts = [genetic_distance(creature.genome, founder) for creature in group]
        metrics[species_id] = SpeciesMetrics(
            species_id=species_id,
            alive=len(group),
            mean_drift=sum(drifts) / len(drifts),
            max_drift=max(drifts),
            near_speciation=sum(1 for drift in drifts if drift >= near_threshold),
            herbivores=sum(1 for creature in group
                           if creature.genome.trait("diet") < DIET_SPLIT),
            carnivores=sum(1 for creature in group
                           if creature.genome.trait("diet") >= DIET_SPLIT),
            mean_age=sum(creature.age for creature in group) / len(group),
        )
    return metrics
