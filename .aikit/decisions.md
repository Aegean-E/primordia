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
