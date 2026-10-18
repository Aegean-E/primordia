"""The creature: one genome plus the mutable per-tick state the engine carries."""

from __future__ import annotations

from dataclasses import dataclass

from primordia.genome import Genome


@dataclass
class Creature:
    """A living agent; `species` stays 0 until the classifier names a lineage."""

    cid: int
    genome: Genome
    x: int
    y: int
    energy: float
    age: int = 0
    alive: bool = True
    species: int = 0
