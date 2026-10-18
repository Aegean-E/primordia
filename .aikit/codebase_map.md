# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `4`
- **Total Classes**: `7`
- **Total Functions / Methods**: `5`
- **Total Source Lines**: `259`

---

## 📦 Modules & Exported Symbols

### [`primordia/__init__.py`](primordia/__init__.py)
> *Primordia: a zero-dependency evolution sandbox - genomes, selection, speciation and a fossil record.*

**Size**: `3` lines (`130` bytes)

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

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

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
