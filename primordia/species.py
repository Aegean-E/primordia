"""Phenetic species: genomes cluster by distance to a founding representative.

A new genome joins the nearest species when it lies within `SPECIATION_DISTANCE` of that
species' founding genome; otherwise it founds a new species that descends from the drifting
lineage. Species never merge, so ids are monotone and the record stays a tree - the shape the
fossil record renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from primordia.genome import Genome, genetic_distance

SPECIATION_DISTANCE = 0.18


@dataclass(frozen=True)
class Species:
    """A named lineage: who founded it, when, and from which species it split."""

    species_id: int
    founder_genome: Genome
    birth_tick: int
    ancestor: int


class SpeciesRegistry:
    """Assigns every genome a species id by distance to each species' founding genome."""

    def __init__(self, distance: float = SPECIATION_DISTANCE) -> None:
        self.distance = distance
        self._members: List[Species] = []

    def __len__(self) -> int:
        return len(self._members)

    def get(self, species_id: int) -> Species:
        """The species record for `species_id`, ids being 1-based in founding order."""
        return self._members[species_id - 1]

    def classify(self, genome: Genome, tick: int, ancestor: int = 0) -> Tuple[int, bool]:
        """The (species_id, is_new) of `genome`; a new species records `ancestor` and `tick`."""
        best_id = 0
        best_distance = 0.0
        for species in self._members:
            distance = genetic_distance(genome, species.founder_genome)
            if best_id == 0 or distance < best_distance:
                best_id, best_distance = species.species_id, distance
        if best_id != 0 and best_distance <= self.distance:
            return best_id, False
        species = Species(species_id=len(self._members) + 1, founder_genome=genome,
                          birth_tick=tick, ancestor=ancestor)
        self._members.append(species)
        return species.species_id, True
