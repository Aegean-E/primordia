# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `23`
- **Total Classes**: `43`
- **Total Functions / Methods**: `66`
- **Total Source Lines**: `2899`

---

## 📦 Modules & Exported Symbols

### [`primordia/__init__.py`](primordia/__init__.py)
> *Primordia: a zero-dependency evolution sandbox - genomes, selection, speciation and a fossil record.*

**Size**: `3` lines (`130` bytes)

---

### [`primordia/__main__.py`](primordia/__main__.py)
> *`python -m primordia` - the command line entry point.*

**Size**: `8` lines (`153` bytes)

---

### [`primordia/analytics.py`](primordia/analytics.py)
> *Small pure statistics over a population: counts by species and mean gene values.*

**Size**: `25` lines (`898` bytes)

**Functions:**
- `def species_counts(creatures)` - *How many living creatures belong to each species id.*
- `def trait_means(creatures)` - *The population's mean value per gene; all zeros for an empty population.*

---

### [`primordia/cli.py`](primordia/cli.py)
> *The command line: run a biosphere, resume one, report on it, or step it interactively.*

**Size**: `262` lines (`10626` bytes)

**Functions:**
- `def main(argv, out, err, stdin)` - *Run one command; returns the exit code: 0 success, 1 failure, 2 usage.*
- `def _build_parser()`
- `def _run(args, out)`
- `def _resume(args, out)`
- `def _stats(args, out)`
- `def _web(args, out)`
- `def _persist_session(engine, path, start_hash, out)` - *Save an observatory session back to its file when the world changed while observed.*
- `def _repl(args, out, stdin)`
- `def _advance(engine, ticks)`
- `def _report(engine, out)`
- `def _summary_line(engine)`
- `def _lineage_line(engine)`
- `def _traits_line(engine)`
- `def _print_species(engine, limit, out)`
- `def _print_fossil(engine, limit, out)`
- `def _count(words, default)`

---

### [`primordia/creature.py`](primordia/creature.py)
> *The creature: one genome plus the mutable per-tick state the engine carries.*

**Size**: `21` lines (`441` bytes)

**Classes:**
- `class Creature` - *A living agent; `species` names the lineage the registry classified it into.*

---

### [`primordia/engine.py`](primordia/engine.py)
> *The deterministic tick loop: metabolism, sensing, action, birth and death.*

**Size**: `400` lines (`18817` bytes)

**Classes:**
- `class Engine` - *The simulation: a world plus its creatures, advanced one deterministic tick at a time.*
  - Method `.__init__(config, seed, founders)`
  - Method `.spawn(genome, x, y, energy)` - *Place one creature on a land tile; the door tests and tools stage a known state with.*
  - Method `.step()` - *Advance one tick: the world updates, then every living creature acts in cid order.*
  - Method `.snapshot_hash()` - *A SHA-256 over the tick and the full creature and food state; equal state, equal hash.*
  - Method `._found(founders)` - *Seed one ancestral species: a viable template with per-founder jitter around it.*
  - Method `._new_creature(genome, x, y, energy, species_id)`
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
  - Method `._richest_tile(creature, radius)` - *The most valuable tile in sight: its stock minus a travel cost per step of distance.*
  - Method `._weakest_prey(hunter, others)`
  - Method `._nearest(creature, candidates)`
  - Method `._die(creature)` - *Death returns the body to the soil at the creature's tile.*
  - Method `._sense_radius(creature)`
  - Method `._satiation(creature)` - *A creature forages until it can afford a litter, then looks for a mate.*
  - Method `._repro_threshold(creature)`
  - Method `._max_age(creature)`
  - Method `._preferred_temperature(creature)`

---

### [`primordia/fossil.py`](primordia/fossil.py)
> *The fossil record: species sightings, peaks, extinction episodes and a bounded event log.*

**Size**: `80` lines (`3179` bytes)

**Classes:**
- `class FossilEvent` - *One durable moment: a speciation or an extinction, with its tick and lineage ids.*
- `class SpeciesTrace` - *One lineage's sighting history, as censuses accumulate.*
- `class FossilRecord` - *Sightings and events per species; one census miss is one extinction episode.*
  - Method `.__init__(event_cap)`
  - Method `.record_speciation(tick, species_id, ancestor, detail)` - *Note a new lineage; the counter is monotonic even when the window forgets.*
  - Method `.census(counts, tick)` - *Update sightings and peaks from one count per species; a census miss is an episode.*
  - Method `._append(event)`

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

### [`primordia/save.py`](primordia/save.py)
> *Persistence: one versioned JSON snapshot carries a whole run across processes.*

**Size**: `278` lines (`10974` bytes)

**Classes:**
- `class SaveError` - *A save could not be read or written; the message carries Why and Fix lines.*
  - Method `.__init__(summary, why, fix)`

**Functions:**
- `def dump_text(engine)` - *The engine's full state as the compact JSON text `save_to` writes.*
- `def save_to(engine, path)` - *Write the engine's full state to `path` atomically, rotating the old file to `.bak`.*
- `def load_from(path)` - *Read a saved engine back; quarantine a corrupt file and fall back to its `.bak`.*
- `def _replace(source, target)` - *`os.replace` with a few immediate retries; a busy indexer or scanner is transient.*
- `def _sync_directory(folder)` - *Ask the OS to persist the rename; not every platform allows opening a folder.*
- `def _quarantine(path)` - *Move a corrupt save aside so it can never be mistaken for a good one.*
- `def _read_json(path)`
- `def _engine_to_data(engine)`
- `def _engine_from_data(data)`
- `def _creature_from(row)`
- `def _species_from(row)`
- `def _fossil_from(data)`

---

### [`primordia/shocks.py`](primordia/shocks.py)
> *God-mode interventions: meteors, blooms, culls and introductions.*

**Size**: `121` lines (`5001` bytes)

**Classes:**
- `class ShockReport` - *What one intervention did, for the operator and the tests.*

**Functions:**
- `def meteor(engine, x, y, radius)` - *Burn a disc: its land tiles lose their food and every creature in it dies unburied.*
- `def bloom(engine, x, y, radius, share)` - *Feed a disc: its land tiles rise toward the food cap without ever passing it.*
- `def cull(engine, share)` - *Thin the population: the weakest share (lowest energy, then lowest cid) is removed.*
- `def introduce(engine, count)` - *Release near-clones of the ancestral lineage onto random land tiles.*
- `def _disc(engine, x, y, radius)` - *Every land tile within `radius` Euclidean steps of `(x, y)`, boundary included.*
- `def _inside(dx, dy, radius)` - *True when an offset lies inside the closed disc of `radius`.*
- `def _check_spot(engine, x, y)`
- `def _check_radius(radius)`
- `def _check_share(share)`

---

### [`primordia/species.py`](primordia/species.py)
> *Phenetic species: genomes cluster by distance to a founding representative.*

**Size**: `64` lines (`2425` bytes)

**Classes:**
- `class Species` - *A named lineage: who founded it, when, and from which species it split.*
- `class SpeciesRegistry` - *Assigns every genome a species id by distance to each species' founding genome.*
  - Method `.__init__(distance)`
  - Method `.__len__()`
  - Method `.get(species_id)` - *The species record for `species_id`, ids being 1-based in founding order.*
  - Method `.from_species(species, distance)` - *Rebuild a registry from stored records, for example when a save resumes.*
  - Method `.classify(genome, tick, ancestor)` - *The (species_id, is_new) of `genome`; a new species records `ancestor` and `tick`.*

---

### [`primordia/web.py`](primordia/web.py)
> *The observatory: a local web view of a running world, with god-mode interventions.*

**Size**: `337` lines (`15518` bytes)

**Functions:**
- `def state_payload(engine)` - *The observable facts of one world, as JSON-ready data.*
- `def render_dashboard(engine, auto, notice)` - *The whole dashboard as one self-contained HTML page.*
- `def _map_html(engine, payload)` - *The tile grid: food shaded green, water blue, creatures dotted by lineage colour.*
- `def _god_forms(cx, cy, width, height)` - *The intervention forms, pre-filled with the world's centre.*
- `def make_handler(engine, lock, quiet)` - *The HTTP handler bound to one engine; every engine touch happens under `lock`.*
- `def make_server(engine, host, port, quiet)` - *A server for `engine` on `(host, port)`; port 0 picks a free one.*
- `def serve(engine, host, port, out)` - *Run the observatory until interrupted; returns the exit code 0.*
- `def _apply_god(engine, path, fields)` - *Map one god-mode POST path onto a shock; bad input raises ValueError.*
- `def _query_int(query, name, default, low, high)`
- `def _field_int(fields, name)`
- `def _field_float(fields, name, default)`
- `def _error_page(message)` - *A refusal page that names what was rejected and how to fix the request.*

---

### [`primordia/world.py`](primordia/world.py)
> *Primordia's world: the tile grid, its food layer and its drifting temperature field.*

**Size**: `116` lines (`5074` bytes)

**Classes:**
- `class WorldConfig` - *The world's shape and pace: fixed at creation and carried by every save.*
  - Method `.__post_init__()`
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

### [`tests/test_analytics.py`](tests/test_analytics.py)
> *Unit tests for the population statistics helpers.*

**Size**: `23` lines (`1040` bytes)

**Classes:**
- `class AnalyticsTests`
  - Method `.test_counts_and_means_on_a_seeded_population()`
  - Method `.test_empty_population_has_no_counts_and_zero_means()`

---

### [`tests/test_cli.py`](tests/test_cli.py)
> *Unit tests for the command line: run, resume, stats and the interactive shell.*

**Size**: `99` lines (`4286` bytes)

**Classes:**
- `class CliTests`
  - Method `.setUp()`
  - Method `.run_cli(argv, stdin)`
  - Method `.test_run_reports_a_summary_and_writes_a_save()`
  - Method `.test_resume_continues_the_saved_history()`
  - Method `.test_stats_prints_population_species_and_fossil_counters()`
  - Method `.test_missing_save_exits_one_with_why_and_fix()`
  - Method `.test_usage_errors_exit_two()`
  - Method `.test_an_impossible_world_exits_two_with_a_fix()`
  - Method `.test_version_flag_prints_the_version()`
  - Method `.test_repl_steps_stats_hashes_saves_and_quits()`
  - Method `.test_repl_survives_unknown_commands()`
  - Method `.test_repl_refuses_zero_row_listings()`
  - Method `.test_the_observatory_persists_session_changes_back_to_its_save()`
  - Method `.test_an_untouched_observatory_leaves_its_save_alone()`

---

### [`tests/test_engine.py`](tests/test_engine.py)
> *Unit tests for the engine: determinism, invariants and the behavioural mechanics.*

**Size**: `201` lines (`8378` bytes)

**Classes:**
- `class DeterminismTests`
  - Method `.test_same_seed_replays_the_same_history()`
  - Method `.test_different_seeds_diverge()`
- `class InvariantTests`
  - Method `.test_creatures_stay_alive_on_land_within_bounds()`
  - Method `.test_world_layers_stay_in_their_ranges()`
  - Method `.test_population_dynamics_move_over_time()`
- `class ResilienceTests`
  - Method `.test_an_empty_world_keeps_ticking_without_incident()`
  - Method `.test_a_dead_world_keeps_ticking_and_records_the_extinction()`
- `class BehaviourTests`
  - Method `.test_grazing_moves_energy_from_the_soil_to_the_grazer()`
  - Method `.test_grazer_grazes_where_it_stands_instead_of_marching_to_equal_stock()`
  - Method `.test_attack_kills_a_weaker_neighbour_and_feeds_the_hunter()`
  - Method `.test_armored_victim_takes_less_damage()`
  - Method `.test_two_creatures_reproduce_and_children_hold_bounded_genomes()`
- `class SpeciesIntegrationTests`
  - Method `.test_founders_start_as_one_species()`
  - Method `.test_census_populates_the_fossil_record()`
  - Method `.test_drift_grows_the_registry_over_time()`
- `class PerformanceTests`
  - Method `.test_a_short_default_run_stays_fast()`

**Functions:**
- `def small_engine(seed, founders, **overrides)`
- `def land_tile(engine)`
- `def adjacent_land(engine)`
- `def staged_genome(mutability, **traits)`

---

### [`tests/test_fossil.py`](tests/test_fossil.py)
> *Unit tests for the fossil record: sightings, peaks, extinctions and the event log.*

**Size**: `46` lines (`1910` bytes)

**Classes:**
- `class CensusTests`
  - Method `.test_census_records_first_last_and_peak()`
  - Method `.test_extinction_when_a_species_leaves_the_census()`
  - Method `.test_extinct_species_can_reappear_without_a_new_speciation()`
  - Method `.test_event_log_is_bounded_and_counters_stay_monotonic()`

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

### [`tests/test_save.py`](tests/test_save.py)
> *Unit tests for persistence: exact round trips, atomic writes, backup fallback and quarantine.*

**Size**: `162` lines (`7340` bytes)

**Classes:**
- `class RoundTripTests`
  - Method `.setUp()`
  - Method `.test_resumed_run_replays_the_same_history()`
  - Method `.test_species_registry_and_fossil_record_survive_the_round_trip()`
  - Method `.test_save_carries_the_format_version()`
  - Method `.test_a_newer_save_version_is_refused_without_quarantine()`
  - Method `.test_a_shocked_world_round_trips_exactly()`
- `class AtomicityTests`
  - Method `.setUp()`
  - Method `.test_overwriting_keeps_the_previous_save_as_a_backup()`
  - Method `.test_a_corrupt_save_falls_back_to_the_backup_and_quarantines_the_wreck()`
  - Method `.test_double_corruption_raises_with_why_and_fix()`
  - Method `.test_missing_file_raises_with_guidance()`
  - Method `.test_a_missing_primary_with_a_live_backup_restores_itself()`
  - Method `.test_a_failed_replace_leaves_no_temp_file()`

**Functions:**
- `def small_config(**overrides)` - *A fast test world; the overrides let a test pin what it stages.*

---

### [`tests/test_species.py`](tests/test_species.py)
> *Unit tests for the species registry: phenetic clustering around founding genomes.*

**Size**: `49` lines (`2048` bytes)

**Classes:**
- `class RegistryTests`
  - Method `.test_first_genome_founds_species_one()`
  - Method `.test_near_clones_join_the_same_species()`
  - Method `.test_far_drift_founds_a_new_species_with_its_ancestor()`
  - Method `.test_representative_is_the_founding_genome()`
  - Method `.test_ids_are_monotonic_and_unique()`

**Functions:**
- `def centered(**traits)`

---

### [`tests/test_web.py`](tests/test_web.py)
> *Unit tests for the observatory: state payload, dashboard, god-mode shocks and the server.*

**Size**: `225` lines (`9585` bytes)

**Classes:**
- `class PayloadTests`
  - Method `.test_state_payload_reports_the_living_world()`
  - Method `.test_state_payload_is_json_ready()`
- `class DashboardTests`
  - Method `.test_dashboard_carries_the_map_the_tables_and_the_controls()`
  - Method `.test_auto_refresh_is_optional()`
- `class MeteorTests`
  - Method `.test_meteor_strips_food_and_kills_within_its_radius()`
- `class BloomTests`
  - Method `.test_bloom_raises_food_toward_the_cap_without_passing_it()`
- `class CullTests`
  - Method `.test_cull_removes_the_weakest_share_deterministically()`
- `class IntroduceTests`
  - Method `.test_introduce_releases_near_clones_of_the_founder_lineage()`
- `class DiscGeometryTests`
  - Method `.test_meteor_and_bloom_sweep_a_disc_not_a_square()`
- `class ValidationTests`
  - Method `.test_shocks_reject_impossible_parameters()`
- `class HttpSmokeTests`
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_dashboard_state_and_save_are_served()`
  - Method `.test_favicon_is_answered_quietly()`
  - Method `.test_an_oversized_form_body_is_refused()`
  - Method `.test_step_query_advances_the_clock()`
  - Method `.test_god_mode_form_mutates_the_world()`

**Functions:**
- `def small_engine(seed, founders, **overrides)`
- `def flat_genome()`
- `def land_tile(engine, skip)`

---

### [`tests/test_world.py`](tests/test_world.py)
> *Unit tests for the world: terrain, the food layer and the temperature field.*

**Size**: `123` lines (`4732` bytes)

**Classes:**
- `class TerrainTests`
  - Method `.test_terrain_is_binary_and_holds_land()`
  - Method `.test_index_and_xy_round_trip()`
  - Method `.test_generation_is_seeded_reproducible()`
- `class FoodTests`
  - Method `.test_land_starts_with_standing_biomass()`
  - Method `.test_food_regrows_but_never_exceeds_the_cap()`
  - Method `.test_water_tiles_are_barren()`
  - Method `.test_take_food_is_bounded_and_leaves_no_debt()`
  - Method `.test_add_food_returns_a_carcass_to_the_soil()`
- `class TemperatureTests`
  - Method `.test_temperature_stays_in_the_unit_interval()`
  - Method `.test_temperature_advances_seasonally()`
  - Method `.test_food_growth_follows_the_season()`
- `class ConfigValidationTests`
  - Method `.test_the_default_config_is_valid()`
  - Method `.test_impossible_configs_are_refused_at_construction()`

**Functions:**
- `def make_world(seed, **overrides)`

---
