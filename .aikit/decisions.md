# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

### ADR-001: A versioned 12-gene normalized genome with all randomness injected

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: Primordia must evolve visibly and stay reproducible: any run replays from its
  seed. That needs a genome small enough to reason about, variation operators that cannot
  leave their declared ranges, and one place where every random draw enters the model.
- **Decision**: A genome is twelve genes normalized to [0, 1] (`GENES` in `primordia/genome.py`):
  size, speed, metabolism, diet, sense, aggression, social, fecundity, lifespan, thermophily,
  curiosity and mutability. `Genome` is frozen and validates length and bounds; `mutate` takes
  a bounded step scaled by the genome's own mutability gene; `crossover` takes whole genes from
  either parent; `genetic_distance` is the root-mean-square gene difference speciation will
  read. Every operator takes an injected `random.Random`; no module draws from the global RNG.
- **Consequences**: One seed plus one tick count reproduces the same history, and tests replay
  it. Gene names and order become a frozen contract once saves exist: changes add genes only,
  bump `GENOME_VERSION` and migrate. Twelve genes cap the search space so speciation clustering
  stays cheap, at the cost of coarse traits.

### ADR-002: A deterministic tick loop with flow-limited forage, size armor and seasonal growth

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: The engine must stay reproducible from one seed while producing an ecology worth
  watching: creatures that forage, compete, breed and die, and selection that visibly moves the
  gene pool. The first balance pass showed creatures stalling one step below breeding condition,
  and a later one showed an unconditional drift to minimum body size.
- **Decision**: One tick advances the world (seasonal food growth and temperature, both with a
  per-tile phase offset) and then every creature in cid order: it pays upkeep scaled by size,
  speed, metabolism and temperature mismatch, ages, forages while below breeding condition
  (hunting first when diet > 0.55 and aggression > 0.35, else grazing the richest tile within
  its sense radius), reproduces when a compatible mate or a rarer asexual birth allows, and
  wanders otherwise. Movement is one tile per stride with a second stride rolled against speed;
  body size insulates a comparable victim from attack damage; deaths return a carcass to the
  soil. Every random draw comes from the engine's one `random.Random`, in fixed order.
- **Consequences**: Determinism is a test (`snapshot_hash` replays exact), and the ecology runs
  at roughly a thousand ticks per second at default size. Under the default constants selection
  converges on small, efficient grazers - an honest basin attractor for a flow-limited world -
  while thermophily and metabolism keep wide spreads (climate sorting, efficiency ratchets).
  The constants are the knob: an environmental shock (the milestone-5 godmode events) or a
  constants change re-opens body size, and any change to them is an ADR-002 amendment.

### ADR-003: Phenetic species, a fossil record, and two ecology repairs the integration forced

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: Milestone 3 adds visible evolution: genomes must cluster into named species,
  speciation must be an event worth watching, and the past must survive in bounded memory.
  Wiring the classifier into the engine exposed two engine flaws that made long runs fragile:
  independent random founders scattered across a hundred species and died on bad draws, and
  creatures chased the single richest tile, herding whole populations onto stripped ground
  while food rotted elsewhere.
- **Decision**: Species are phenetic and tree-shaped: `SpeciesRegistry` keeps each lineage's
  founding genome, a genome joins the nearest species when `genetic_distance` to that founder
  is at most `SPECIATION_DISTANCE` (0.18), and otherwise founds a new species that records its
  ancestor and birth tick. Species never merge; ids are 1-based, monotone and never reused.
  `FossilRecord` censuses the living population each tick into one `SpeciesTrace` per species
  (first and last seen, peak population, extinction tick) plus a bounded event log of
  speciations and extinctions, while the counters stay monotone even when old events drop.
  Founders are one ancestral species: a template drawn from the survivable ranges of the cost
  genes (metabolism, size, speed, sense, thermophily, diet) is jittered by `FOUNDER_JITTER`
  per founder, so the lineage starts with real variance inside one species. Two repairs ride
  along: the world starts with standing biomass (`initial_food_share`), and a tile is valued as
  its stock minus a travel cost per step, so creatures graze where they stand when local food
  is good and only walk when the walk pays.
- **Consequences**: A default-world run now sustains roughly ninety to a hundred and ninety
  creatures across seeds through four thousand ticks, radiating fifteen to a hundred species
  with visible extinctions, at about a thousand ticks per second; small test worlds still
  wobble between booms and crashes, which is the honest ecology, so tests that need radiation
  pin a seed with measured margin. This amends ADR-002: the forage rule reads best-value tile,
  not richest tile, and the world no longer starts barren; the rest of ADR-002 stands. A save
  must carry species ids and the fossil counters, so milestone 4 serializes them (G-002).

### ADR-004: One versioned JSON save with atomic rotation, and a command line that resumes it exactly

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: A run that only lives in RAM dies with the process: watching evolution needs
  pause and resume, and the web observatory (milestone 5) needs a state file to read. Resuming
  must not disturb the replay contract - the resumed run has to produce the same future as the
  uninterrupted one - which means the save must carry everything the engine would have kept,
  including the raw state of its random number generator.
- **Decision**: `primordia/save.py` writes one versioned JSON snapshot (`SAVE_VERSION`) holding
  the world's four layers, every creature, the species registry, the fossil record and
  `random.Random.getstate()`, plus seed, tick and next cid. Writes are atomic: a temp file is
  flushed and fsynced, the previous save rotates to `.bak`, `os.replace` moves the new file in
  with retries, and the folder is fsynced where the platform allows. A corrupt primary is
  quarantined as `.corrupt_<stamp>`, the `.bak` is loaded and written back; when neither is
  usable, `SaveError` explains why and what to do. `primordia/cli.py` (with `__main__.py`) gives
  the same engine four doors - `run`, `resume` (in place), `stats` and an interactive `repl` -
  with injected streams, `Why:`/`Fix:` failures, exit codes 0/1/2 and a `primordia` console
  script in `pyproject.toml`.
- **Consequences**: A save is a text file anyone can read and diff; it weighs about 93 KB at
  default size after three thousand ticks, the RNG state alone being 625 integers - honest, and
  the web UI can parse the same shape. Resume-exactness is a test: save, load, step both and
  compare `snapshot_hash` and cids, plus a CLI run pinned against a fresh in-process run.
  Locking stays out on purpose: `os.replace` guarantees a reader never sees a half-written
  file, and the design has one writer per save. `SaveError` messages are the pattern for every
  later failure surface, including the web observatory.

### ADR-005: A server-rendered observatory, and god mode as pure state mutations

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: Watching evolution should not require writing code: a run needs a view. The
  project is zero-dependency, so the view must come from the standard library alone - no
  framework, no front-end build, no third-party requests - and it must read the same state the
  CLI already owns, without forking the engine or its save format. What the milestone plan
  calls god mode must push a world around without breaking the replay contract.
- **Decision**: `primordia/web.py` serves one engine through `http.server`: the dashboard is
  server-rendered HTML (map, counters, species table, fossil events), `?step=N` advances the
  clock before rendering, `?step=N&auto=S` adds a meta refresh for auto-play, `/state.json`
  serves the observable facts as data and `/save` downloads the standard save file. God-mode
  interventions live in `primordia/shocks.py` - `meteor`, `bloom`, `cull` and `introduce` - as
  pure mutations of state the engine already carries, each returning a small `ShockReport`.
  Requests are serialized under one lock, refused with a 400 page carrying `Why:` and `Fix:`,
  and successful posts redirect with the report in the notice banner.
- **Consequences**: The dashboard renders a default world in about a millisecond (63 KB of
  HTML) and the state endpoint in well under one; the suite covers the payload, the dashboard,
  all four shocks and one real-socket smoke. Because shocks add no state, the save version
  stays 1 and a shocked world resumes exactly - a future sustained-climate shock would need
  stored world state and a save-version bump, so it waits. The observatory steps only the
  ticks the operator asked for; it never advances a world behind their back.

### ADR-006: MIT license and the 1.0.0 release

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: The project is public, and a repository without a license is not legally usable;
  the six planned milestones are done, so the work needs a version to name it by.
- **Decision**: Primordia ships under the MIT license (`LICENSE`) and is versioned 1.0.0 in
  `primordia/__init__.py`, `pyproject.toml` and `python -m primordia --version`; the release is
  tagged `v1.0.0` in git and on GitHub.
- **Consequences**: Anyone may use, study, share and modify the sandbox. The save format stays
  version 1, and everything the ADRs promise holds at this tag - re-verified before it: a
  10,000-tick default run (about 800 ticks per second, deterministic across a save and reload at
  tick 5,000, 183 creatures over 69 species), a bounded fossil log at 173 events, and the
  83-test suite on the milestone-6 checklist.

### ADR-007: Audit fixes - honest shock geometry, protected saves, validated configs

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: A post-release audit of 1.0.0 found four classes of defects. The shock
  documentation promises discs, but `meteor` and `bloom` swept a Chebyshev square. `load_from`
  treated a save written by a different `SAVE_VERSION` as corruption: it quarantined the file
  and could overwrite the primary from `.bak`, destroying the newer save. `WorldConfig`
  accepted values that break deep inside the tick loop (`day_length=0` divides by zero) or
  silently degrade a run. And the observatory lost every operator-driven change - session
  steps and all god-mode interventions - when the server exited.
- **Decision**: `meteor`, `bloom` and their `_disc` helper sweep a true Euclidean disc
  (distance squared at most radius squared, boundary inclusive). A save version this build
  cannot read raises `SaveError` with `Why:` and `Fix:` lines and is never quarantined. A
  missing primary with a live `.bak` restores itself on load, and a failed replace removes its
  temp file. `WorldConfig` validates its shape, pace, food, water and season ranges at
  construction, and the CLI turns that `ValueError` into a `Fix:`-carrying exit code 2. The
  observatory sends `Cache-Control: no-store`, answers `/favicon.ico` with 204, caps POST
  bodies at 4 KiB, and `web PATH` saves operator-driven changes back to the file on exit when
  the state changed (compared by `snapshot_hash`). The REPL refuses a zero-row listing count
  instead of quietly showing ten rows.
- **Consequences**: version 1.0.1. Shock geometry matches its name and the README; a save is
  quarantined only when it truly fails to parse, and version mismatches keep their file
  intact; crash windows between the two replaces have a recovery path; impossible configs fail
  loudly at construction, so `python -m primordia run --width 0` exits 2 with a message rather
  than building a zero-tile world. Determinism is untouched: the disc change alters which
  tiles a shock touches, not the order of any draw, and the suite still replays fixed seeds
  exactly.

### ADR-008: Filesystem and socket edges carry the same Why and Fix promise

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: A second review of 1.0.1 found failure paths that still traceback, hang or
  destroy state. `save_to` onto a folder renamed the folder to `.bak`; `load_from` on a folder
  raised a raw `IsADirectoryError`; JSON without a version field fell through as a crash; a
  quarantine whose `os.replace` failed escaped as an `OSError`. In the observatory, a malformed
  `Content-Length` crashed the handler thread, a negative one made `read(-n)` wait for EOF, an
  out-of-range port raised `OverflowError`, `web --ticks` silently dropped its pre-roll because
  the session hash was sampled after the advance, and a bind beyond loopback exposed a mutating
  server without warning anyone.
- **Decision**: `save_to` refuses a directory path before touching the filesystem. `load_from`
  detects a directory (or an unreadable file) and raises `SaveError` with `Why:` and `Fix:`
  lines; the same happens when a corrupt file cannot be quarantined, leaving the file in place.
  JSON that is not an object or has no `version` key is reported as "not a primordia save" and
  is never quarantined. The observatory validates `Content-Length` before reading (whole,
  non-negative, within the 4 KiB cap), refuses anything else with the 400 page and closes the
  connection. `serve` turns a refused bind into a `SaveError` that asks for another port, and
  prints a no-authentication warning when the bound address is not loopback. The web session
  hash is captured before `--ticks` advance, so the pre-roll persists on exit like every other
  operator change while a bare view remains read-only.
- **Consequences**: version 1.0.2. The `Why:`/`Fix:` contract now holds on the filesystem and
  socket edges: no destructive rename, no request thread stuck reading, and no silent loss of
  requested work. The engine, save format and determinism are untouched, so existing saves
  still load and replay exactly.

### ADR-009: Live neighbour bookkeeping, treated snapshots and a full-state hash

- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: A full-code audit found defects that the earlier releases missed. The engine
  built one spatial hash at the start of a tick and never updated it, so every later creature
  queried its neighbours at start-of-tick positions: a victim that had moved away could still
  be struck and a mate that had moved into range was invisible. The founders were jittered
  around a template but the first jittered genome founded species 1, so 17 of 300 tested seeds
  split the herd into two species at tick 0. `WorldConfig` accepted `1.5` tiles and `NaN`
  fields, which failed later inside `range()`/arithmetic. A parseable save with a short layer or
  an out-of-bounds creature loaded and crashed the next tick with `IndexError`. `snapshot_hash`
  covered only creatures and food, so RNG-only divergence was invisible, and the analytics
  helpers counted dead creatures despite their docstrings.
- **Decision**: The neighbour hash is updated in `_move`, `_die` and `_birth`, and a newborn
  killed in its birth tick is not retained. The ancestral template is classified as species 1
  before the jittered founders are spawned, making one species a structural guarantee because
  the jitter is at most 0.15 RMS inside the 0.18 threshold. `WorldConfig` requires integer
  shapes and paces plus finite numeric fields; `Engine.spawn` requires integer coordinates and
  finite non-negative energy. `load_from` verifies the snapshot before returning: layer sizes
  and ranges, unique cids, land bounds, species references, sequential registry ids and
  ancestors, birth ticks, fossil traces/events and log capacity. `dump_text` sets
  `allow_nan=False`, and `save_to` turns the resulting refusal into a `SaveError`. The hash now
  covers the RNG state, terrain, phases, temperature, registry and fossil record. Analytics
  ignore dead creatures.
- **Consequences**: version 1.0.3. Interactions now use actual positions, at the cost of
  removing the creature from its old bucket on every move; selection outcomes change where
  stale versus live positions differed, but determinism and the save schema are unchanged. A
  malformed save that previously loaded is now quarantined with `Why:`/`Fix:` instead of
  crashing later, and non-finite state is refused rather than written. The richer hash costs
  about 1 ms per call on a populated world and is only computed on demand.

### ADR-010: Blocked steps, exact round trips and treated snapshot dates

- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: The fourth full-code audit found five gaps past 1.0.3. `_move_towards` built a
  step for both axes even when one delta was zero, so a creature whose direct tile was water
  stepped sideways and a second stride could carry it away from the target. `Engine.spawn`
  stored an integer energy unchanged while `load_from` restores floats, so `spawn(...,
  energy=45)` changed the snapshot hash across a save/load. Saves omitted the species
  registry's threshold, so an engine with a custom distance reloaded at 0.18. Shock parameters
  were only compared, so a float coordinate reached `range()` as a `TypeError` and a string
  share failed a comparison. Snapshot verification checked layer shapes and creature bounds
  but trusted negative or future ages, impossible fossil windows, extinction ticks beyond the
  snapshot and events whose ancestor was outside the lineage.
- **Decision**: Steps are built only from nonzero deltas, larger axis first, so a blocked
  direct step waits or takes the other axis. `spawn` normalizes energy to a float, and
  `SpeciesRegistry` normalizes its threshold to a float. Saves carry `species_distance`;
  files without the field load at 0.18, and a non-finite or negative threshold is refused.
  Every shock checks whole-number x/y/radius/count and a boolean-free finite share before
  use. `load_from` refuses ages outside `[0, tick]`, sighting windows where `first_seen >
  last_seen` or `last_seen > tick`, extinction ticks beyond the snapshot, and events with a
  tick outside the run or `0 <= ancestor < species_id`.
- **Consequences**: version 1.0.4. A blocked direct step no longer turns into a sidestep, so
  fixed-seed histories change where the old sidestep happened; valid saves still replay
  exactly, and the format version stays 1 because the new field is optional and old files use
  the documented default. Malformed snapshots that previously loaded are now quarantined with
  `Why:`/`Fix:`, and direct shock API misuse raises a readable `ValueError` instead of a
  `TypeError`. Engine determinism for valid states, the save schema's existing fields and the
  web/CLI contracts are otherwise unchanged.

### ADR-011: Web observatory cladogram, ecology time-series charts and macro shocks

- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: The Web Observatory provided tile-map rendering, species counts and four localized
  shocks, but lacked tools to track evolutionary history over extended runs: operators could not
  visualize the phylogenetic cladogram of radiating lineages or monitor population and trait
  dynamics over time. Additionally, operators needed macro-level interventions to test environmental
  pressures (global cooling) and mutagenic radiation bursts.
- **Decision**: Added two new god-mode interventions to `primordia/shocks.py` and the web UI:
  `ice_age` (chills land food across the grid and imposes thermophily-scaled energy stress) and
  `radiation_burst` (samples living creatures deterministically via the engine RNG, mutates their
  genomes, and immediately records speciations if genetic distance exceeds the threshold). Both
  shocks mutate only state the engine already carries, preserving save schema version 1 and replay
  determinism. `state_payload` now includes a complete `lineage` array (every species in the
  registry, its ancestor, birth tick, living population, peak and extinction tick).
  `build_phylogeny_svg` renders an interactive orthogonal cladogram SVG displaying all ancestral
  connections, color-coded living/extinct status nodes, and rich tooltip metadata.
  `build_population_svg` and `build_traits_svg` generate crisp inline SVG charts tracking
  population, living species, and five key trait trajectories (diet, size, speed, metabolism,
  thermophily) over session history. `/history.json` serves the recorded time-series.
- **Consequences**: version 1.0.5. The observatory becomes an interactive evolutionary workbench
  with zero third-party dependencies and 100% offline standard-library rendering. Save format
  schemas and engine determinism contracts remain completely intact. 10 new tests bring the unit
  suite tally from 132 to 142 tests.

### ADR-012: Lineage drift observability in analytics, the CLI and the observatory

- **Date**: 2026-10-20
- **Status**: Accepted
- **Context**: Speciation is the sandbox's headline mechanic, but the tooling only exposed raw
  population counts, global trait means and post-hoc fossil events. An operator could see that a
  lineage had split only after a new species appeared; nothing reported how far a living lineage
  had drifted from its founder, how many of its creatures stood near the speciation threshold, or
  how its diet was divided. The observatory's species table repeated the same population facts.
- **Decision**: `analytics.species_metrics` returns one frozen `SpeciesMetrics` per living
  species: mean and worst `genetic_distance` to that species' founding genome, the count of
  creatures at or beyond 80% of `registry.distance` (`NEAR_SPECIATION_FRACTION`), a
  herbivore/carnivore split at the 0.5 diet gene, and mean age. Drift is reported raw so it can
  be compared with the registry's threshold. The CLI prints a "closest to speciation" line in
  every report and adds drift, near, diet and age to each `species` row; `state_payload` adds
  `drift`, `max_drift`, `near_speciation`, `herbivores` and `carnivores` to each living species
  row, and the dashboard renders drift, near and diet columns.
- **Consequences**: version 1.0.6. The metrics are a pure read over the current population: no
  engine, RNG, save-schema or replay change, and every existing CLI token, JSON key and table
  column survives. Drift is measured against each lineage's own founder by construction, so a
  young species starts at zero drift even when it split far from its ancestor's founder. 8 new
  tests bring the unit suite tally from 142 to 150 tests.

### ADR-013: Drift shares survive a zero speciation threshold

- **Date**: 2026-10-20
- **Status**: Accepted
- **Context**: The review of ADR-012 found that `_drift_line` and `_print_species` divided the
  mean drift by `registry.distance` without guarding it. `save.py` refuses only a negative or
  non-finite `species_distance`, so a save carrying `0.0` loads, and `stats` or
  `repl ... species` then raised an uncaught `ZeroDivisionError` instead of a readable report.
- **Decision**: One `_threshold_share` helper renders the drift share and reports "no positive
  threshold" when the distance is zero or negative; both report sites use it. A regression test
  loads a save, sets the registry distance to zero, saves it, and runs `stats` and `species` to
  assert exit code 0 and the fallback text.
- **Consequences**: Reports no longer crash on a zero threshold and the JSON payload is
  unchanged. A zero threshold remains an accepted (if degenerate) configuration where every
  creature is its own founder; the loader's contract is untouched. 1 new test brings the unit
  suite tally from 150 to 151 tests.
