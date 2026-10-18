# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `9`
- **Total Classes**: `18`
- **Total Functions / Methods**: `10`
- **Total Source Lines**: `964`

---

## 📦 Modules & Exported Symbols

### [`primordia/__init__.py`](primordia/__init__.py)
> *Primordia: a zero-dependency evolution sandbox - genomes, selection, speciation and a fossil record.*

**Size**: `3` lines (`130` bytes)

---

### [`primordia/creature.py`](primordia/creature.py)
> *The creature: one genome plus the mutable per-tick state the engine carries.*

**Size**: `21` lines (`436` bytes)

**Classes:**
- `class Creature` - *A living agent; `species` stays 0 until the classifier names a lineage.*

---

### [`primordia/engine.py`](primordia/engine.py)
> *The deterministic tick loop: metabolism, sensing, action, birth and death.*

**Size**: `357` lines (`16493` bytes)

**Classes:**
- `class Engine` - *The simulation: a world plus its creatures, advanced one deterministic tick at a time.*
  - Method `.__init__(config, seed, founders)`
  - Method `.spawn(genome, x, y, energy)` - *Place one creature on a land tile; the door tests and tools stage a known state with.*
  - Method `.step()` - *Advance one tick: the world updates, then every living creature acts in cid order.*
  - Method `.snapshot_hash()` - *A SHA-256 over the tick and the full creature and food state; equal state, equal hash.*
  - Method `._found(founders)` - *Seed the first population from random land tiles, biased toward grazing habits.*
  - Method `._new_creature(genome, x, y, energy)`
  - Method `._neighbour_hash()` - *Living creatures by tile index; bucket order is cid order, so scans stay deterministic.*
  - Method `._nearby(creature, radius, buckets)` - *Living others within `radius` tiles, in a deterministic tile-then-bucket order.*
  - Method `._tick_creature(creature, buckets, newborns)`
  - Method `._pay_upkeep(creature)`
  - Method `._seek_energy(creature, buckets)`
  - Method `._graze(creature)` - *Eat from the current tile; a pure hunter (diet 1) takes nothing.*
  - Method `._attack(hunter, victim)` - *One strike; size shields a comparable victim, and a kill feeds the hunter.*
  - Method `._try_reproduce(creature, buckets)` - *A litter when energy allows and a mate shares the genome; asexual births are rarer.*
  - Method `._birth(parent, parents)` - *Invest energy into a litter; each child mixes or copies the parental genomes, then mutates.*
  - Method `._wander(creature, buckets)` - *Idle motion: a social pull toward a neighbour first, then a curious random stroll.*
  - Method `._move_towards(creature, x, y)` - *Step one tile toward (x, y), preferring the larger axis; a fast creature may stride twice.*
  - Method `._move(creature, x, y)`
  - Method `._random_free_neighbour(creature)`
  - Method `._richest_tile(creature, radius)`
  - Method `._weakest_prey(hunter, others)`
  - Method `._nearest(creature, candidates)`
  - Method `._die(creature)` - *Death returns the body to the soil at the creature's tile.*
  - Method `._sense_radius(creature)`
  - Method `._satiation(creature)` - *A creature forages until it can afford a litter, then looks for a mate.*
  - Method `._repro_threshold(creature)`
  - Method `._max_age(creature)`
  - Method `._preferred_temperature(creature)`

---

### [`primordia/genome.py`](primordia/genome.py)
> *Primordia genomes: a fixed vector of bounded genes and the operators that vary them.*

**Size**: `113` lines (`5006` bytes)

**Classes:**
- `class GeneSpec` - *One gene: the normalized range it lives in and what the engine decodes it to.*
- `class Genome` - *An immutable gene vector; every gene lies inside its `GeneSpec` range.*
  - Method `.__post_init__()`
  - Method `.trait(name)` - *The value of gene `name`, so readers decode by meaning rather than by index.*
  - Method `.as_dict()` - *The genome as a name-to-value mapping, the shape the save format and web UI read.*
  - Method `.from_dict(data)` - *Rebuild a genome from `as_dict` output; a missing gene raises KeyError.*

**Functions:**
- `def random_genome(rng)` - *A fresh genome with every gene drawn uniformly from its range.*
- `def mutate(genome, rng)` - *A child genome: each gene mutates with `MUTATION_CHANCE_PER_GENE`, then clamps.*
- `def crossover(parent_a, parent_b, rng)` - *A child genome assembled from whole genes of either parent, a coin flip per gene.*
- `def genetic_distance(a, b)` - *Root-mean-square gene difference in [0, 1]; species clustering reads this.*

---

### [`primordia/world.py`](primordia/world.py)
> *Primordia's world: the tile grid, its food layer and its drifting temperature field.*

**Size**: `92` lines (`3707` bytes)

**Classes:**
- `class WorldConfig` - *The world's shape and pace: fixed at creation and carried by every save.*
- `class World` - *A mutable tile grid: terrain, a regrowing food layer and a seasonal temperature field.*
  - Method `.__init__(config, rng)`
  - Method `.length()` - *The number of tiles in the grid.*
  - Method `.index(x, y)` - *The flat storage index of tile (x, y).*
  - Method `.xy(index)` - *The (x, y) of a flat storage index.*
  - Method `.is_land(x, y)` - *True when (x, y) is inside the grid and dry.*
  - Method `.update(tick)` - *One tick of the world: the season drives food growth and the temperature field.*
  - Method `.take_food(index, amount)` - *Remove and return up to `amount` of food; a water tile holds none.*
  - Method `.add_food(index, amount)` - *Return nutrients to a land tile, never past the food cap.*

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/test_engine.py`](tests/test_engine.py)
> *Unit tests for the engine: determinism, invariants and the behavioural mechanics.*

**Size**: `141` lines (`5976` bytes)

**Classes:**
- `class DeterminismTests`
  - Method `.test_same_seed_replays_the_same_history()`
  - Method `.test_different_seeds_diverge()`
- `class InvariantTests`
  - Method `.test_creatures_stay_alive_on_land_within_bounds()`
  - Method `.test_world_layers_stay_in_their_ranges()`
  - Method `.test_population_dynamics_move_over_time()`
- `class BehaviourTests`
  - Method `.test_grazing_moves_energy_from_the_soil_to_the_grazer()`
  - Method `.test_attack_kills_a_weaker_neighbour_and_feeds_the_hunter()`
  - Method `.test_armored_victim_takes_less_damage()`
  - Method `.test_two_creatures_reproduce_and_children_hold_bounded_genomes()`
- `class PerformanceTests`
  - Method `.test_two_hundred_ticks_stay_fast()`

**Functions:**
- `def small_engine(seed, founders, **overrides)`
- `def land_tile(engine)`
- `def adjacent_land(engine)`
- `def staged_genome(mutability, **traits)`

---

### [`tests/test_genome.py`](tests/test_genome.py)
> *Unit tests for the genome model: bounds, determinism and the variation operators.*

**Size**: `143` lines (`5919` bytes)

**Classes:**
- `class GeneCatalogTests`
  - Method `.test_names_are_unique_and_indexes_match()`
- `class GenomeModelTests`
  - Method `.test_random_genome_is_full_length_and_bounded()`
  - Method `.test_random_genome_is_seeded_reproducible()`
  - Method `.test_genome_rejects_wrong_length()`
  - Method `.test_genome_rejects_out_of_range_gene()`
  - Method `.test_genome_is_immutable()`
  - Method `.test_trait_reads_by_name()`
  - Method `.test_as_dict_and_from_dict_round_trip()`
  - Method `.test_from_dict_requires_every_gene()`
- `class MutationTests`
  - Method `.test_mutation_never_leaves_bounds()`
  - Method `.test_mutation_is_seeded_reproducible()`
  - Method `.test_mutation_changes_genes_over_time()`
  - Method `.test_mutability_gene_scales_the_step()`
  - Method `._drift(genome, seed)`
- `class CrossoverTests`
  - Method `.test_child_genes_come_whole_from_either_parent()`
  - Method `.test_crossover_mixes_both_parents_across_seeds()`
  - Method `.test_crossover_is_seeded_reproducible()`
- `class DistanceTests`
  - Method `.test_distance_is_zero_symmetric_and_bounded()`

**Functions:**
- `def genome_with(mutability)` - *A genome centered at 0.5 with one chosen mutability gene.*

---

### [`tests/test_world.py`](tests/test_world.py)
> *Unit tests for the world: terrain, the food layer and the temperature field.*

**Size**: `94` lines (`3659` bytes)

**Classes:**
- `class TerrainTests`
  - Method `.test_terrain_is_binary_and_holds_land()`
  - Method `.test_index_and_xy_round_trip()`
  - Method `.test_generation_is_seeded_reproducible()`
- `class FoodTests`
  - Method `.test_food_regrows_but_never_exceeds_the_cap()`
  - Method `.test_water_tiles_are_barren()`
  - Method `.test_take_food_is_bounded_and_leaves_no_debt()`
  - Method `.test_add_food_returns_a_carcass_to_the_soil()`
- `class TemperatureTests`
  - Method `.test_temperature_stays_in_the_unit_interval()`
  - Method `.test_temperature_advances_seasonally()`
  - Method `.test_food_growth_follows_the_season()`

**Functions:**
- `def make_world(seed, **overrides)`

---
