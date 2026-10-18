# primordia

Primordia is a zero-dependency evolution sandbox: seed a biosphere, run its clock, and watch
genomes vary, compete and speciate. A run replays exactly from its seed, and a fossil record
keeps the story of what happened.

> **Status**: milestone 3 of 6 - the genome model, the world, the deterministic engine, the
> species classifier and the fossil record are in place; persistence, the CLI and the web
> observatory arrive in the next milestones.

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
├── .gitignore                <- transient AIKit state and Python caches excluded
├── README.md
├── pyproject.toml            <- build and package configuration
├── primordia/                <- core package
│   ├── __init__.py           <- package metadata
│   ├── analytics.py          <- population statistics: counts by species, mean traits
│   ├── creature.py           <- one genome plus the engine's mutable per-tick state
│   ├── engine.py             <- the deterministic tick loop
│   ├── fossil.py             <- the fossil record: sightings, peaks and events per species
│   ├── genome.py             <- bounded genes and variation operators
│   ├── species.py            <- phenetic species: genomes cluster by genetic distance
│   └── world.py              <- tile grid, food layer and temperature field
└── tests/                    <- unit test suite
    ├── __init__.py
    ├── test_analytics.py     <- species counts and trait means
    ├── test_engine.py        <- determinism, invariants and behavioural mechanics
    ├── test_fossil.py        <- censuses, extinction and the bounded event log
    ├── test_genome.py        <- gene bounds, mutation, crossover and distance
    ├── test_species.py       <- classification, ancestry and monotone species ids
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

The world is a tile grid of land and water. Every land tile carries a food layer that starts as
standing biomass, then regrows with the season (each tile on its own phase, so booms and famines
travel across the map), under a temperature field that drifts between a north-south gradient and
the seasonal sine.

One engine tick is one fixed sequence: the world updates first, then every creature acts in
ascending cid order. A creature pays upkeep (size, speed, metabolism, temperature mismatch),
ages, and either forages while it is below breeding condition - hunting the weakest reachable
weaker neighbour when its genes allow, otherwise grazing the best tile it can sense, its stock
discounted by the walk, so it grazes where it stands when local food is good instead of herding
onto one maximum - or reproduces when a compatible mate is near, or wanders. Attacks are
softened by a comparable body (armor), movement is one tile per stride with a second stride
rolled against speed, and a dead body returns to the soil as food for the next generation.

Determinism is the contract: every random draw comes from one seeded `random.Random` in a fixed
order, so the same seed replays the same history exactly - a property the suite checks by
comparing state hashes after identical runs.

## 🦕 Species & The Fossil Record

A species is phenetic: the registry keeps each lineage's founding genome, and a new genome joins
the nearest species when it lies within `SPECIATION_DISTANCE` of that founder; beyond it, the
drifting lineage founds a new species and names its ancestor. Species never merge, so ids stay
monotone and the record is a tree. The founders themselves are one ancestral species - a
template drawn from the survivable ranges of the cost genes, jittered per founder - so evolution
starts with real variance inside one lineage.

Each tick the engine censuses the living population. The fossil record keeps one trace per
species (first and last seen, peak population, extinction tick) plus a bounded event log of
speciations and extinctions; the counters stay monotone even when the window forgets an old
event, so a long run costs bounded memory and still tells its whole story.

## 🧪 Development

The unit suite runs with:

```bash
python -m unittest discover
```

53 tests replay fixed seeds: gene bounds and seeded reproducibility for the variation
operators; terrain, standing biomass, growth and temperature invariants for the world;
classification, ancestry and monotone ids for the species registry; censuses, extinction and
the bounded event log for the fossil record; population statistics; and for the engine,
byte-identical replays of the same seed, world and creature invariants over long runs, staged
grazing and hunting mechanics, armored-defense arithmetic, a drift-to-speciation run and a
performance smoke test.
