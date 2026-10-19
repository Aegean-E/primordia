"""God-mode interventions: meteors, blooms, culls and introductions.

Each intervention mutates only state the engine already carries - the food layer, the living
creatures, the registry's ancestral genome - and returns a small report. None of them adds
state of its own, so a shocked world still saves, loads and resumes exactly (ADR-005).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from primordia.engine import FOUNDER_JITTER, Engine
from primordia.genome import Genome
from primordia.world import LAND

MAX_RADIUS = 12
MAX_INTRODUCTION = 60


@dataclass(frozen=True)
class ShockReport:
    """What one intervention did, for the operator and the tests."""

    action: str
    detail: str
    tiles: int = 0
    creatures: int = 0


def meteor(engine: Engine, x: int, y: int, radius: int) -> ShockReport:
    """Burn a disc: its land tiles lose their food and every creature in it dies unburied."""
    _check_spot(engine, x, y)
    _check_radius(radius)
    tiles = 0
    for tx, ty in _disc(engine, x, y, radius):
        engine.world.food[engine.world.index(tx, ty)] = 0.0
        tiles += 1
    killed = 0
    for creature in engine.creatures:
        if creature.alive and _inside(creature.x - x, creature.y - y, radius):
            creature.alive = False
            creature.energy = 0.0
            killed += 1
    engine.creatures = [creature for creature in engine.creatures if creature.alive]
    return ShockReport("meteor", f"radius {radius} at ({x}, {y})", tiles=tiles, creatures=killed)


def bloom(engine: Engine, x: int, y: int, radius: int, share: float = 1.0) -> ShockReport:
    """Feed a disc: its land tiles rise toward the food cap without ever passing it."""
    _check_spot(engine, x, y)
    _check_radius(radius)
    _check_share(share)
    cap = engine.world.config.food_cap
    tiles = 0
    for tx, ty in _disc(engine, x, y, radius):
        tile = engine.world.index(tx, ty)
        engine.world.food[tile] = min(cap, engine.world.food[tile] + cap * share)
        tiles += 1
    return ShockReport("bloom", f"share {share:g} radius {radius} at ({x}, {y})", tiles=tiles)


def cull(engine: Engine, share: float) -> ShockReport:
    """Thin the population: the weakest share (lowest energy, then lowest cid) is removed."""
    _check_share(share)
    living = sorted((creature for creature in engine.creatures if creature.alive),
                    key=lambda creature: (creature.energy, creature.cid))
    doomed = int(len(living) * share)
    for creature in living[:doomed]:
        creature.alive = False
        creature.energy = 0.0
    engine.creatures = [creature for creature in engine.creatures if creature.alive]
    return ShockReport("cull", f"share {share:g}", creatures=doomed)


def introduce(engine: Engine, count: int) -> ShockReport:
    """Release near-clones of the ancestral lineage onto random land tiles."""
    _check_whole("count", count)
    if not 1 <= count <= MAX_INTRODUCTION:
        raise ValueError(f"count must be between 1 and {MAX_INTRODUCTION}")
    if len(engine.registry) == 0:
        raise ValueError("the world has no ancestral lineage to clone")
    if not any(terrain == LAND for terrain in engine.world.terrain):
        raise ValueError("the world holds no land to live on")
    founder = engine.registry.get(1).founder_genome
    land_tiles = [tile for tile in range(engine.world.length)
                  if engine.world.terrain[tile] == LAND]
    for _ in range(count):
        tile = engine.rng.choice(land_tiles)
        genes = tuple(min(1.0, max(0.0, value + engine.rng.uniform(-FOUNDER_JITTER, FOUNDER_JITTER)))
                      for value in founder.genes)
        x, y = engine.world.xy(tile)
        engine.spawn(Genome(genes=genes), x, y)
    return ShockReport("introduce", f"{count} near-clones of species 1", creatures=count)


def _disc(engine: Engine, x: int, y: int, radius: int):
    """Every land tile within `radius` Euclidean steps of `(x, y)`, boundary included."""
    for ty in range(max(0, y - radius), min(engine.config.height - 1, y + radius) + 1):
        for tx in range(max(0, x - radius), min(engine.config.width - 1, x + radius) + 1):
            if _inside(tx - x, ty - y, radius) and engine.world.is_land(tx, ty):
                yield tx, ty


def _inside(dx: int, dy: int, radius: int) -> bool:
    """True when an offset lies inside the closed disc of `radius`."""
    return dx * dx + dy * dy <= radius * radius


def _check_whole(name: str, value: object) -> None:
    """Refuse floats and booleans before they reach a range() or a tile index."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a whole number, got {value!r}")


def _check_spot(engine: Engine, x: int, y: int) -> None:
    _check_whole("x", x)
    _check_whole("y", y)
    if not (0 <= x < engine.config.width and 0 <= y < engine.config.height):
        raise ValueError(f"({x}, {y}) is outside the {engine.config.width}x"
                         f"{engine.config.height} world")


def _check_radius(radius: int) -> None:
    _check_whole("radius", radius)
    if not 1 <= radius <= MAX_RADIUS:
        raise ValueError(f"radius must be between 1 and {MAX_RADIUS}")


def _check_share(share: float) -> None:
    if isinstance(share, bool) or not isinstance(share, (int, float)):
        raise ValueError(f"share must be a number between 0 and 1, got {share!r}")
    if not math.isfinite(share) or not 0.0 < share <= 1.0:
        raise ValueError("share must be greater than 0 and at most 1")
