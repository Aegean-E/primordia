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
