# primordia

Primordia is a zero-dependency evolution sandbox: seed a biosphere, run its clock, and watch
genomes vary, compete and speciate. A run replays exactly from its seed, and a fossil record
keeps the story of what happened.

> **Status**: milestone 1 of 6 - the genome model is in place; the world, engine, CLI and the
> web observatory arrive in the next milestones.

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
│   └── genome.py             <- bounded genes and variation operators
└── tests/                    <- unit test suite
    ├── __init__.py
    └── test_genome.py        <- gene bounds, mutation, crossover and distance
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

## 🧪 Development

The unit suite runs with:

```bash
python -m unittest discover
```

It replays the variation operators against fixed seeds: gene bounds, seeded reproducibility,
crossover gene inheritance, genetic distance, and the property that a higher `mutability` gene
takes larger mutation steps.
