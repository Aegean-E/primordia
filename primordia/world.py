"""Primordia's world: the tile grid, its food layer and its drifting temperature field.

The world owns three flat per-tile layers: immutable terrain, a food layer that starts as
standing biomass and regrows toward a cap, and a temperature field that advances with the
season and varies by latitude and a per-tile phase offset. The engine reads the layers; only
the engine mutates them through `take_food`/`add_food`, so every quantity stays in its declared
range.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

LAND = 0
WATER = 1
TWO_PI = 2.0 * math.pi


def _require_int(name: str, value: object, minimum: int) -> None:
    """Refuse non-integer shapes and paces before they reach a range() or an index."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")


def _require_finite(name: str, value: object) -> None:
    """Refuse strings, NaN and infinity, which poison arithmetic without raising early."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class WorldConfig:
    """The world's shape and pace: fixed at creation and carried by every save."""

    width: int = 36
    height: int = 18
    food_cap: float = 10.0
    food_regrowth: float = 0.12
    initial_food_share: float = 0.5
    day_length: int = 400
    water_ratio: float = 0.12
    temperature_swing: float = 0.30
    season_amplitude: float = 0.75

    def __post_init__(self) -> None:
        _require_int("width", self.width, 1)
        _require_int("height", self.height, 1)
        _require_int("day_length", self.day_length, 1)
        for name in ("food_cap", "food_regrowth", "initial_food_share", "water_ratio",
                     "temperature_swing", "season_amplitude"):
            _require_finite(name, getattr(self, name))
        if self.food_cap <= 0.0:
            raise ValueError(f"food_cap must be positive, got {self.food_cap}")
        if self.food_regrowth < 0.0:
            raise ValueError(f"food_regrowth cannot be negative, got {self.food_regrowth}")
        if not 0.0 <= self.initial_food_share <= 1.0:
            raise ValueError(
                f"initial_food_share must be within [0, 1], got {self.initial_food_share}")
        if not 0.0 <= self.water_ratio <= 1.0:
            raise ValueError(f"water_ratio must be within [0, 1], got {self.water_ratio}")
        if self.temperature_swing < 0.0:
            raise ValueError(
                f"temperature_swing cannot be negative, got {self.temperature_swing}")
        if not 0.0 <= self.season_amplitude <= 1.0:
            raise ValueError(
                f"season_amplitude must be within [0, 1], got {self.season_amplitude}")


class World:
    """A mutable tile grid: terrain, a regrowing food layer and a seasonal temperature field."""

    def __init__(self, config: WorldConfig, rng: random.Random) -> None:
        self.config = config
        size = config.width * config.height
        self.terrain: List[int] = [
            WATER if rng.random() < config.water_ratio else LAND for _ in range(size)
        ]
        self.phase: List[float] = [rng.random() * TWO_PI for _ in range(size)]
        standing = config.food_cap * config.initial_food_share
        self.food: List[float] = [standing if tile == LAND else 0.0 for tile in self.terrain]
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
