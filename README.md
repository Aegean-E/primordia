# primordia

Primordia is a zero-dependency evolution sandbox: seed a biosphere, run its clock, and watch
genomes vary, compete and speciate. A run replays exactly from its seed, and a fossil record
keeps the story of what happened.

> **Status**: milestone 2 of 6 - the genome model, the world and the deterministic engine are
> in place; the species classifier, the CLI and the web observatory arrive in the next milestones.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10+ (standard library only - zero third-party packages) and git.
- **Canonical Regression Shield Gate**:
  ```bash
  python aikit.py check primordia
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status primordia` |
| Phase 4: every gate | `python aikit.py check primordia` |
| Repair memory and map, then check | `python aikit.py fix primordia` |
| Resume an interrupted task | `python aikit.py resume primordia` |

## 📦 What's Inside

```text
primordia/
├── .aikit/                   <- project memory: record, ledger, decisions, map
├── .gitignore                <- transient AIKit state excluded
├── README.md
├── pyproject.toml            <- build and package configuration
├── primordia/                <- core package
│   ├── __init__.py           <- package metadata
│   ├── creature.py           <- one genome plus the engine's mutable per-tick state
│   ├── engine.py             <- the deterministic tick loop
│   ├── genome.py             <- bounded genes and variation operators
│   └── world.py              <- tile grid, food layer and temperature field
└── tests/                    <- unit test suite
    ├── __init__.py
    ├── test_engine.py        <- determinism, invariants and behavioural mechanics
    ├── test_genome.py        <- gene bounds, mutation, crossover and distance
    └── test_world.py         <- terrain, food and temperature
```

## 🧬 The Genome

A genome is twelve genes normalized to [0, 1]; the engine decodes them into physical traits.
Variation operators never leave the declared ranges, and every random draw comes from one
injected `random.Random`, so `same seed => same history` is a contract the tests replay.

| Gene | What it steers |
|---|---|
| `size` | body size: more energy capacity and defense, higher upkeep |
| `speed` | tiles moved per tick, paid for in energy |
| `metabolism` | metabolic efficiency: slow burn versus fast burn |
| `diet` | foraging mode: 0 grazes plants, 1 hunts other creatures |
| `sense` | perception radius for food, threats and mates |
| `aggression` | readiness to attack rather than avoid a neighbor |
| `social` | attraction to kin and crowds versus solitude |
| `fecundity` | offspring per successful reproduction |
| `lifespan` | resistance to aging and starvation damage |
| `thermophily` | preferred temperature band of the world |
| `curiosity` | wandering drive versus staying put in plenty |
| `mutability` | own mutation rate: how far its children may stray |

## 🌍 The World & The Engine

The world is a tile grid of land and water. Every land tile carries a food layer that regrows
with the season (each tile on its own phase, so booms and famines travel across the map) and a
temperature field that drifts between a north-south gradient and the seasonal sine.

One engine tick is one fixed sequence: the world updates first, then every creature acts in
ascending cid order. A creature pays upkeep (size, speed, metabolism, temperature mismatch),
ages, and either forages while it is below breeding condition - hunting the weakest reachable
weaker neighbour when its genes allow, otherwise grazing the richest tile it can sense - or
reproduces when a compatible mate is near, or wanders. Attacks are softened by a comparable
body (armor), movement is one tile per stride with a second stride rolled against speed, and a
dead body returns to the soil as food for the next generation.

Determinism is the contract: every random draw comes from one seeded `random.Random` in a fixed
order, so the same seed replays the same history exactly - a property the suite checks by
comparing state hashes after identical runs.

## 🧪 Development

The unit suite runs with:

```bash
python -m unittest discover
```

37 tests replay fixed seeds: gene bounds and seeded reproducibility for the variation
operators; terrain, food, growth and temperature invariants for the world; and for the engine,
byte-identical replays of the same seed, world and creature invariants over long runs, staged
grazing and hunting mechanics, armored-defense arithmetic, and a performance smoke test.
