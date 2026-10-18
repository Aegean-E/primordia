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
