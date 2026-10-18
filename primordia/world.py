"""Primordia's world: the tile grid, its food layer and its drifting temperature field.

The world owns three flat per-tile layers: immutable terrain, a food layer that regrows
toward a cap, and a temperature field that advances with the season and varies by latitude
and a per-tile phase offset. The engine reads the layers; only the engine mutates them
through `take_food`/`add_food`, so every quantity stays in its declared range.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

LAND = 0
WATER = 1
TWO_PI = 2.0 * math.pi


@dataclass(frozen=True)
class WorldConfig:
    """The world's shape and pace: fixed at creation and carried by every save."""

    width: int = 36
    height: int = 18
    food_cap: float = 10.0
    food_regrowth: float = 0.12
    day_length: int = 400
    water_ratio: float = 0.12
    temperature_swing: float = 0.30
    season_amplitude: float = 0.75


class World:
    """A mutable tile grid: terrain, a regrowing food layer and a seasonal temperature field."""

    def __init__(self, config: WorldConfig, rng: random.Random) -> None:
        self.config = config
        size = config.width * config.height
        self.terrain: List[int] = [
            WATER if rng.random() < config.water_ratio else LAND for _ in range(size)
        ]
        self.phase: List[float] = [rng.random() * TWO_PI for _ in range(size)]
        self.food: List[float] = [0.0] * size
        self.temperature: List[float] = [0.0] * size

    @property
    def length(self) -> int:
        """The number of tiles in the grid."""
        return self.config.width * self.config.height

    def index(self, x: int, y: int) -> int:
        """The flat storage index of tile (x, y)."""
        return y * self.config.width + x

    def xy(self, index: int) -> Tuple[int, int]:
        """The (x, y) of a flat storage index."""
        return index % self.config.width, index // self.config.width

    def is_land(self, x: int, y: int) -> bool:
        """True when (x, y) is inside the grid and dry."""
        if not 0 <= x < self.config.width or not 0 <= y < self.config.height:
            return False
        return self.terrain[self.index(x, y)] == LAND

    def update(self, tick: int) -> None:
        """One tick of the world: the season drives food growth and the temperature field."""
        swing = self.config.temperature_swing
        amplitude = self.config.season_amplitude
        for y in range(self.config.height):
            warmth = 0.12 + 0.55 * (y / max(1, self.config.height - 1))
            for x in range(self.config.width):
                tile = self.index(x, y)
                season = 0.5 + 0.5 * math.sin(TWO_PI * tick / self.config.day_length + self.phase[tile])
                self.temperature[tile] = min(1.0, max(0.0, warmth + swing * (2.0 * season - 1.0)))
                if self.terrain[tile] == LAND:
                    growth = self.config.food_regrowth * ((1.0 - amplitude) + amplitude * season)
                    self.food[tile] = min(self.config.food_cap, self.food[tile] + growth)

    def take_food(self, index: int, amount: float) -> float:
        """Remove and return up to `amount` of food; a water tile holds none."""
        if self.terrain[index] != LAND:
            return 0.0
        taken = min(self.food[index], max(0.0, amount))
        self.food[index] -= taken
        return taken

    def add_food(self, index: int, amount: float) -> None:
        """Return nutrients to a land tile, never past the food cap."""
        if self.terrain[index] == LAND:
            self.food[index] = min(self.config.food_cap, self.food[index] + max(0.0, amount))
