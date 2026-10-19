"""The deterministic tick loop: metabolism, sensing, action, birth and death.

One `random.Random` drives every draw in a fixed order, so a seed plus a tick count replays
the same history exactly, and `snapshot_hash` proves it. Each tick, the world updates first;
then every creature acts in ascending cid order: it pays upkeep and ages, forages until it can
afford a litter (hunting if its genes allow, otherwise grazing the best tile in sight, its
stock discounted by the walk),
reproduces when a mate is near, and wanders otherwise. Dead bodies return to the soil as food.
Births are classified into species by distance from the founding genomes, and a census each tick
keeps the fossil record honest.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Dict, List, Optional, Tuple

from primordia.analytics import species_counts
from primordia.creature import Creature
from primordia.fossil import FossilRecord
from primordia.genome import GENES, Genome, crossover, genetic_distance, mutate
from primordia.species import SpeciesRegistry
from primordia.world import LAND, World, WorldConfig

# Life budget: founders are sampled around one ancestral template drawn from the survivable
# ranges of the cost genes, so the lineage starts as a single species that can persist.
START_ENERGY = 45.0
FOUNDER_JITTER = 0.15
FOUNDER_BASE_RANGES = {
    "metabolism": (0.45, 1.00),
    "size": (0.05, 0.60),
    "speed": (0.00, 0.55),
    "sense": (0.20, 0.80),
    "thermophily": (0.10, 0.85),
    "diet": (0.00, 0.35),
}
# Upkeep: paid every tick, scaled by body and habits; temperature mismatch costs extra.
UPKEEP_BASE = 0.10
UPKEEP_SIZE = 0.06
UPKEEP_SPEED = 0.10
UPKEEP_METABOLISM_SPAN = 0.75
TEMPERATURE_MISMATCH_COST = 0.35
PREFERRED_TEMPERATURE_BASE = 0.20
PREFERRED_TEMPERATURE_SPAN = 0.60
# Movement: one tile per stride, a fast creature may take a second stride toward its target.
MOVE_COST_BASE = 0.06
MOVE_COST_SIZE = 0.20
MOVE_COST_SPEED = 0.25
STRIDE_CHANCE_PER_SPEED = 0.60
SENSE_RADIUS_BASE = 1
SENSE_RADIUS_GAIN = 3
# Foraging: falling below breeding condition opens the food search; grazing scales with
# herbivory, hunting with size. A tile is valued as stock minus a travel cost per step, so
# creatures graze where they stand when local food is good and never herd onto one maximum.
FORAGE_MIN_VALUE = 0.0
FORAGE_DISTANCE_COST = 0.35
GRAZE_BITE_BASE = 1.10
GRAZE_BITE_SIZE = 1.90
HUNT_AGGRESSION_MIN = 0.35
HUNT_DIET_MIN = 0.55
HUNT_DAMAGE_BASE = 3.0
HUNT_DAMAGE_SIZE = 9.0
HUNT_COST = 1.0
HUNT_ENERGY_GAIN = 0.45
PREY_SIZE_MARGIN = 0.95
DEFENSE_FLOOR = 0.25
DEFENSE_SHARE = 0.60
CARCASS_BASE = 0.30
CARCASS_SIZE = 1.40
# Reproduction: a surplus over the threshold buys a litter; compatible genes invite a mate.
REPRO_THRESHOLD_BASE = 50.0
REPRO_THRESHOLD_SIZE = 30.0
REPRO_INVEST_SHARE = 0.35
REPRO_CHANCE_BASE = 0.05
REPRO_CHANCE_FECUNDITY = 0.10
ASEXUAL_CHANCE_SHARE = 0.40
MATE_DISTANCE = 0.25
MATE_ENERGY_SHARE = 0.60
OFFSPRING_PER_FECUNDITY = 2
# Aging
MAX_AGE_BASE = 140
MAX_AGE_LIFESPAN_GAIN = 360


class Engine:
    """The simulation: a world plus its creatures, advanced one deterministic tick at a time."""

    def __init__(self, config: WorldConfig = WorldConfig(), seed: int = 0,
                 founders: int = 60) -> None:
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)
        self.world = World(config, self.rng)
        self.registry = SpeciesRegistry()
        self.fossil = FossilRecord()
        self.tick = 0
        self.next_cid = 1
        self.creatures: List[Creature] = []
        self._found(founders)
        self.world.update(self.tick)

    def spawn(self, genome: Genome, x: int, y: int, energy: float = START_ENERGY) -> Creature:
        """Place one creature on a land tile; the door tests and tools stage a known state with."""
        if isinstance(x, bool) or not isinstance(x, int) or isinstance(y, bool) or not isinstance(y, int):
            raise ValueError(f"coordinates must be whole numbers, got ({x!r}, {y!r})")
        if (isinstance(energy, bool) or not isinstance(energy, (int, float))
                or not math.isfinite(energy) or energy < 0.0):
            raise ValueError(f"energy must be a non-negative finite number, got {energy!r}")
        energy = float(energy)
        if not self.world.is_land(x, y):
            raise ValueError(f"({x}, {y}) is not a land tile; creatures live on land only")
        species_id, is_new = self.registry.classify(genome, self.tick)
        if is_new and species_id > 1:
            self.fossil.record_speciation(self.tick, species_id, ancestor=0, detail="introduced")
        creature = self._new_creature(genome, x, y, energy, species_id)
        self.creatures.append(creature)
        return creature

    def step(self) -> None:
        """Advance one tick: the world updates, then every living creature acts in cid order."""
        self.world.update(self.tick)
        buckets = self._neighbour_hash()
        newborns: List[Creature] = []
        for creature in self.creatures:
            if creature.alive:
                self._tick_creature(creature, buckets, newborns)
        for creature in self.creatures:
            if creature.alive and creature.energy <= 0.0:
                self._die(creature, buckets)
        self.creatures = [creature for creature in self.creatures if creature.alive]
        self.creatures.extend(creature for creature in newborns if creature.alive)
        self.fossil.census(species_counts(self.creatures), self.tick)
        self.tick += 1

    def snapshot_hash(self) -> str:
        """A SHA-256 over the full replay state: tick, RNG, world, creatures, species and fossil."""
        digest = hashlib.sha256()

        def feed(text: str) -> None:
            digest.update(text.encode("utf-8"))

        feed(f"tick={self.tick};next={self.next_cid};seed={self.seed};config={self.config!r};")
        feed(f"rng={self.rng.getstate()!r};")
        for creature in self.creatures:
            feed(f"{creature.cid}|{creature.x}|{creature.y}|{creature.age}"
                 f"|{creature.alive}|{creature.species}|{creature.energy!r}"
                 f"|{creature.genome.genes!r}|")
        for name in ("terrain", "phase", "food", "temperature"):
            feed(f"{name}={getattr(self.world, name)!r};")
        feed(f"registry_distance={self.registry.distance!r};")
        for species_id in range(1, len(self.registry) + 1):
            species = self.registry.get(species_id)
            feed(f"species={species.species_id}|{species.founder_genome.genes!r}"
                 f"|{species.birth_tick}|{species.ancestor};")
        feed(f"fossil_cap={self.fossil.event_cap};speciations={self.fossil.speciations}"
             f";extinctions={self.fossil.extinctions};")
        for species_id in sorted(self.fossil.traces):
            trace = self.fossil.traces[species_id]
            feed(f"trace={species_id}|{trace.first_seen}|{trace.last_seen}"
                 f"|{trace.peak_population}|{trace.extinct_tick};")
        for event in self.fossil.events:
            feed(f"event={event.tick}|{event.kind}|{event.species_id}|{event.ancestor}"
                 f"|{event.detail};")
        return digest.hexdigest()

    def _found(self, founders: int) -> None:
        """Seed one ancestral species: a viable template with per-founder jitter around it."""
        land_tiles = [tile for tile in range(self.world.length)
                      if self.world.terrain[tile] == LAND]
        if founders <= 0 or not land_tiles:
            return
        template = Genome(genes=tuple(
            self.rng.uniform(*FOUNDER_BASE_RANGES.get(gene.name, (gene.low, gene.high)))
            for gene in GENES
        ))
        # The template itself is species 1, so the jitter (at most 0.15 per gene, hence at
        # most 0.15 root-mean-square) can never exceed the 0.18 speciation distance.
        self.registry.classify(template, self.tick)
        self.rng.shuffle(land_tiles)
        for tile in land_tiles[:min(founders, len(land_tiles))]:
            genes = tuple(min(1.0, max(0.0, value + self.rng.uniform(-FOUNDER_JITTER, FOUNDER_JITTER)))
                          for value in template.genes)
            x, y = self.world.xy(tile)
            self.spawn(Genome(genes=genes), x, y)

    def _new_creature(self, genome: Genome, x: int, y: int, energy: float,
                      species_id: int) -> Creature:
        creature = Creature(cid=self.next_cid, genome=genome, x=x, y=y, energy=energy,
                            species=species_id)
        self.next_cid += 1
        return creature

    def _neighbour_hash(self) -> Dict[int, List[Creature]]:
        """Living creatures by tile index; membership is kept current as they move and die."""
        buckets: Dict[int, List[Creature]] = {}
        for creature in self.creatures:
            if creature.alive:
                index = self.world.index(creature.x, creature.y)
                buckets.setdefault(index, []).append(creature)
        return buckets

    def _nearby(self, creature: Creature, radius: int,
                buckets: Dict[int, List[Creature]]) -> List[Creature]:
        """Living others within `radius` tiles, in a deterministic tile-then-bucket order."""
        others: List[Creature] = []
        y_min = max(0, creature.y - radius)
        y_max = min(self.config.height - 1, creature.y + radius)
        x_min = max(0, creature.x - radius)
        x_max = min(self.config.width - 1, creature.x + radius)
        for y in range(y_min, y_max + 1):
            row = y * self.config.width
            for x in range(x_min, x_max + 1):
                for other in buckets.get(row + x, ()):
                    if other is not creature and other.alive:
                        others.append(other)
        return others

    def _tick_creature(self, creature: Creature, buckets: Dict[int, List[Creature]],
                       newborns: List[Creature]) -> None:
        self._pay_upkeep(creature)
        creature.age += 1
        if creature.energy <= 0.0 or creature.age > self._max_age(creature):
            self._die(creature, buckets)
            return
        if creature.energy < self._satiation(creature):
            self._seek_energy(creature, buckets)
            return
        children = self._try_reproduce(creature, buckets)
        if children:
            newborns.extend(children)
        else:
            self._wander(creature, buckets)

    def _pay_upkeep(self, creature: Creature) -> None:
        genome = creature.genome
        upkeep = UPKEEP_BASE + UPKEEP_SIZE * genome.trait("size") + UPKEEP_SPEED * genome.trait("speed")
        upkeep *= 1.25 - UPKEEP_METABOLISM_SPAN * genome.trait("metabolism")
        tile = self.world.index(creature.x, creature.y)
        mismatch = abs(self.world.temperature[tile] - self._preferred_temperature(creature))
        creature.energy -= upkeep + TEMPERATURE_MISMATCH_COST * mismatch

    def _seek_energy(self, creature: Creature, buckets: Dict[int, List[Creature]]) -> None:
        radius = self._sense_radius(creature)
        if (creature.genome.trait("diet") > HUNT_DIET_MIN
                and creature.genome.trait("aggression") > HUNT_AGGRESSION_MIN):
            victim = self._weakest_prey(creature, self._nearby(creature, radius, buckets))
            if victim is not None:
                self._attack(creature, victim, buckets)
                return
        tile = self._richest_tile(creature, radius)
        if tile is not None:
            if tile != (creature.x, creature.y):
                self._move_towards(creature, tile[0], tile[1], buckets)
            self._graze(creature)
        else:
            self._wander(creature, buckets)

    def _graze(self, creature: Creature) -> float:
        """Eat from the current tile; a pure hunter (diet 1) takes nothing."""
        herbivory = 1.0 - creature.genome.trait("diet")
        bite = herbivory * (GRAZE_BITE_BASE + GRAZE_BITE_SIZE * creature.genome.trait("size"))
        if bite <= 0.0:
            return 0.0
        tile = self.world.index(creature.x, creature.y)
        taken = self.world.take_food(tile, bite)
        creature.energy += taken
        return taken

    def _attack(self, hunter: Creature, victim: Creature,
                buckets: Dict[int, List[Creature]]) -> None:
        """One strike; size shields a comparable victim, and a kill feeds the hunter."""
        hunter.energy -= HUNT_COST
        prey_energy = max(0.0, victim.energy)
        hunter_size = hunter.genome.trait("size")
        ratio = victim.genome.trait("size") / (hunter_size + 1e-9)
        armor = DEFENSE_SHARE * max(0.0, min(1.0, (ratio - DEFENSE_FLOOR) / (1.0 - DEFENSE_FLOOR)))
        victim.energy -= (HUNT_DAMAGE_BASE + HUNT_DAMAGE_SIZE * hunter_size) * (1.0 - armor)
        if victim.energy <= 0.0:
            self._die(victim, buckets)
            hunter.energy += HUNT_ENERGY_GAIN * prey_energy

    def _try_reproduce(self, creature: Creature, buckets: Dict[int, List[Creature]]) -> List[Creature]:
        """A litter when energy allows and a mate shares the genome; asexual births are rarer."""
        if creature.energy <= self._repro_threshold(creature):
            return []
        radius = self._sense_radius(creature)
        candidates = [
            other for other in self._nearby(creature, radius, buckets)
            if genetic_distance(creature.genome, other.genome) <= MATE_DISTANCE
            and other.energy > MATE_ENERGY_SHARE * self._repro_threshold(other)
        ]
        mate = self._nearest(creature, candidates)
        chance = REPRO_CHANCE_BASE + REPRO_CHANCE_FECUNDITY * creature.genome.trait("fecundity")
        if mate is not None:
            if self.rng.random() < chance:
                return self._birth(creature, (creature, mate), buckets)
        elif self.rng.random() < chance * ASEXUAL_CHANCE_SHARE:
            return self._birth(creature, (creature,), buckets)
        return []

    def _birth(self, parent: Creature, parents: Tuple[Creature, ...],
               buckets: Dict[int, List[Creature]]) -> List[Creature]:
        """Invest energy into a litter; each child mixes or copies the parental genomes, then mutates."""
        invest = REPRO_INVEST_SHARE * parent.energy
        parent.energy -= invest
        count = 1 + int(OFFSPRING_PER_FECUNDITY * parent.genome.trait("fecundity"))
        share = invest / count
        children = []
        for _ in range(count):
            if len(parents) == 2:
                base = crossover(parents[0].genome, parents[1].genome, self.rng)
            else:
                base = parent.genome
            genome = mutate(base, self.rng)
            species_id, is_new = self.registry.classify(genome, self.tick, ancestor=parent.species)
            if is_new:
                self.fossil.record_speciation(self.tick, species_id, ancestor=parent.species)
            child = self._new_creature(genome, parent.x, parent.y, share, species_id)
            buckets.setdefault(self.world.index(child.x, child.y), []).append(child)
            children.append(child)
        return children

    def _wander(self, creature: Creature, buckets: Dict[int, List[Creature]]) -> None:
        """Idle motion: a social pull toward a neighbour first, then a curious random stroll."""
        social_draw = self.rng.random()
        curiosity_draw = self.rng.random()
        if social_draw < creature.genome.trait("social"):
            partner = self._nearest(creature, self._nearby(creature, self._sense_radius(creature),
                                                           buckets))
            if partner is not None:
                self._move_towards(creature, partner.x, partner.y, buckets)
                return
        if curiosity_draw < creature.genome.trait("curiosity"):
            target = self._random_free_neighbour(creature)
            if target is not None:
                self._move_towards(creature, target[0], target[1], buckets)

    def _move_towards(self, creature: Creature, x: int, y: int,
                      buckets: Dict[int, List[Creature]]) -> None:
        """Step one tile toward (x, y), preferring the larger axis; a fast creature may stride twice."""
        if (x, y) == (creature.x, creature.y):
            return
        dx, dy = x - creature.x, y - creature.y
        steps: List[Tuple[int, int]] = []
        if dx:
            steps.append((1 if dx > 0 else -1, 0))
        if dy:
            steps.append((0, 1 if dy > 0 else -1))
        if abs(dx) < abs(dy):
            steps.reverse()
        for step_x, step_y in steps:
            target = (creature.x + step_x, creature.y + step_y)
            if not self.world.is_land(*target):
                continue
            self._move(creature, target[0], target[1], buckets)
            if (creature.x, creature.y) == (x, y):
                return
            speed = creature.genome.trait("speed")
            if self.rng.random() < STRIDE_CHANCE_PER_SPEED * speed:
                second = (creature.x + step_x, creature.y + step_y)
                if self.world.is_land(*second):
                    self._move(creature, second[0], second[1], buckets)
            return

    def _move(self, creature: Creature, x: int, y: int,
              buckets: Dict[int, List[Creature]]) -> None:
        """Move one tile and keep the neighbour hash pointing at the creature's new tile."""
        old_index = self.world.index(creature.x, creature.y)
        old_bucket = buckets.get(old_index)
        if old_bucket is not None and creature in old_bucket:
            old_bucket.remove(creature)
        creature.x, creature.y = x, y
        buckets.setdefault(self.world.index(x, y), []).append(creature)
        genome = creature.genome
        creature.energy -= (MOVE_COST_BASE + MOVE_COST_SIZE * genome.trait("size")
                            + MOVE_COST_SPEED * genome.trait("speed"))

    def _random_free_neighbour(self, creature: Creature) -> Optional[Tuple[int, int]]:
        candidates = [(creature.x + dx, creature.y + dy)
                      for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                      if self.world.is_land(creature.x + dx, creature.y + dy)]
        return self.rng.choice(candidates) if candidates else None

    def _richest_tile(self, creature: Creature, radius: int) -> Optional[Tuple[int, int]]:
        """The most valuable tile in sight: its stock minus a travel cost per step of distance.

        Local stock competes on fair terms with distant plenty, so a creature grazes where it
        stands when the yield is comparable and only walks when the walk pays. Tiles that do
        not repay the trip are ignored, and a barren neighbourhood sends its owner wandering.
        """
        best: Optional[Tuple[int, int]] = None
        best_value = FORAGE_MIN_VALUE
        y_min = max(0, creature.y - radius)
        y_max = min(self.config.height - 1, creature.y + radius)
        x_min = max(0, creature.x - radius)
        x_max = min(self.config.width - 1, creature.x + radius)
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                tile = self.world.index(x, y)
                if self.world.terrain[tile] != LAND:
                    continue
                distance = max(abs(x - creature.x), abs(y - creature.y))
                value = self.world.food[tile] - FORAGE_DISTANCE_COST * distance
                if value > best_value:
                    best_value = value
                    best = (x, y)
        return best

    def _weakest_prey(self, hunter: Creature, others: List[Creature]) -> Optional[Creature]:
        margin = hunter.genome.trait("size") * PREY_SIZE_MARGIN
        prey = [other for other in others if other.genome.trait("size") <= margin]
        if not prey:
            return None
        return min(prey, key=lambda other: (other.genome.trait("size"), other.cid))

    def _nearest(self, creature: Creature, candidates: List[Creature]) -> Optional[Creature]:
        if not candidates:
            return None
        return min(candidates, key=lambda other: (max(abs(other.x - creature.x), abs(other.y - creature.y)),
                                                  other.cid))

    def _die(self, creature: Creature, buckets: Dict[int, List[Creature]]) -> None:
        """Death returns the body to the soil and removes the creature from the neighbour hash."""
        creature.alive = False
        tile = self.world.index(creature.x, creature.y)
        bucket = buckets.get(tile)
        if bucket is not None and creature in bucket:
            bucket.remove(creature)
        self.world.add_food(tile, CARCASS_BASE + CARCASS_SIZE * creature.genome.trait("size"))

    def _sense_radius(self, creature: Creature) -> int:
        return SENSE_RADIUS_BASE + int(SENSE_RADIUS_GAIN * creature.genome.trait("sense"))

    def _satiation(self, creature: Creature) -> float:
        """A creature forages until it can afford a litter, then looks for a mate."""
        return self._repro_threshold(creature)

    def _repro_threshold(self, creature: Creature) -> float:
        return REPRO_THRESHOLD_BASE + REPRO_THRESHOLD_SIZE * creature.genome.trait("size")

    def _max_age(self, creature: Creature) -> int:
        return int(MAX_AGE_BASE + MAX_AGE_LIFESPAN_GAIN * creature.genome.trait("lifespan"))

    def _preferred_temperature(self, creature: Creature) -> float:
        return PREFERRED_TEMPERATURE_BASE + PREFERRED_TEMPERATURE_SPAN * creature.genome.trait("thermophily")
