"""Persistence: one versioned JSON snapshot carries a whole run across processes.

A save holds everything the engine needs to replay its future exactly: the world's layers,
every creature, the species registry, the fossil record and the raw state of the engine's
`random.Random`. Writes are atomic - a temp file is flushed and fsynced, the previous save
rotates to `.bak`, and `os.replace` swaps the new file in with retries - so a crash leaves
either the old save or the new one, never half of either. A corrupt primary is quarantined and
the `.bak` takes over; when no usable file remains, `SaveError` says why and what to do.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Union

from primordia.creature import Creature
from primordia.engine import Engine
from primordia.fossil import FossilEvent, FossilRecord, SpeciesTrace
from primordia.genome import Genome
from primordia.species import Species, SpeciesRegistry
from primordia.world import WorldConfig

SAVE_VERSION = 1
BACKUP_SUFFIX = ".bak"
REPLACE_ATTEMPTS = 5
REPLACE_PAUSE = 0.05


class SaveError(Exception):
    """A save could not be read or written; the message carries Why and Fix lines."""

    def __init__(self, summary: str, why: str, fix: str) -> None:
        super().__init__(f"{summary}\nWhy: {why}\nFix: {fix}")
        self.summary = summary
        self.why = why
        self.fix = fix


def save_to(engine: Engine, path: Union[str, Path]) -> Path:
    """Write the engine's full state to `path` atomically, rotating the old file to `.bak`."""
    path = Path(path)
    payload = json.dumps(_engine_to_data(engine), separators=(",", ":"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + f".tmp_{os.getpid()}")
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            _replace(path, Path(str(path) + BACKUP_SUFFIX))
        _replace(temp, path)
        _sync_directory(path.parent)
    except OSError as error:
        raise SaveError(
            f"could not write the save to {path}",
            why=f"the filesystem refused the write ({error})",
            fix="check that the folder exists and is writable, then try again",
        ) from error
    return path


def load_from(path: Union[str, Path]) -> Engine:
    """Read a saved engine back; quarantine a corrupt file and fall back to its `.bak`."""
    path = Path(path)
    if not path.exists():
        raise SaveError(
            f"save not found: {path}",
            why="no file exists at that path",
            fix="check the path, or start a new run with `python -m primordia run --save <path>`",
        )
    try:
        return _engine_from_data(_read_json(path))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        wreck = _quarantine(path)
        backup = Path(str(path) + BACKUP_SUFFIX)
        if backup.exists():
            try:
                engine = _engine_from_data(_read_json(backup))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                engine = None
            if engine is not None:
                save_to(engine, path)
                return engine
        raise SaveError(
            f"could not read the save at {path}",
            why=f"the file is corrupt and no usable backup remains ({error});"
                f" the wreck is kept at {wreck}",
            fix="start a new run with `python -m primordia run --save <path>`",
        ) from error


def _replace(source: Path, target: Path) -> None:
    """`os.replace` with a few immediate retries; a busy indexer or scanner is transient."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except OSError:
            if attempt + 1 == REPLACE_ATTEMPTS:
                raise
            time.sleep(REPLACE_PAUSE)


def _sync_directory(folder: Path) -> None:
    """Ask the OS to persist the rename; not every platform allows opening a folder."""
    try:
        handle = os.open(folder, os.O_RDONLY)  # hygiene: allow bare descriptor, closed below
    except OSError:
        return
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _quarantine(path: Path) -> Path:
    """Move a corrupt save aside so it can never be mistaken for a good one."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    wreck = path.with_name(path.name + f".corrupt_{stamp}")
    index = 1
    while wreck.exists():
        wreck = path.with_name(path.name + f".corrupt_{stamp}-{index}")
        index += 1
    os.replace(path, wreck)
    return wreck


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _engine_to_data(engine: Engine) -> Dict[str, Any]:
    state = engine.rng.getstate()
    return {
        "version": SAVE_VERSION,
        "seed": engine.seed,
        "tick": engine.tick,
        "next_cid": engine.next_cid,
        "config": asdict(engine.config),
        "rng": {"version": state[0], "state": list(state[1]), "gauss_next": state[2]},
        "world": {
            "terrain": list(engine.world.terrain),
            "phase": list(engine.world.phase),
            "food": list(engine.world.food),
            "temperature": list(engine.world.temperature),
        },
        "creatures": [
            {
                "cid": creature.cid,
                "genes": list(creature.genome.genes),
                "x": creature.x,
                "y": creature.y,
                "energy": creature.energy,
                "age": creature.age,
                "alive": creature.alive,
                "species": creature.species,
            }
            for creature in engine.creatures
        ],
        "species": [
            {
                "id": engine.registry.get(species_id).species_id,
                "genes": list(engine.registry.get(species_id).founder_genome.genes),
                "birth_tick": engine.registry.get(species_id).birth_tick,
                "ancestor": engine.registry.get(species_id).ancestor,
            }
            for species_id in range(1, len(engine.registry) + 1)
        ],
        "fossil": {
            "event_cap": engine.fossil.event_cap,
            "speciations": engine.fossil.speciations,
            "extinctions": engine.fossil.extinctions,
            "traces": {
                str(species_id): {
                    "first_seen": trace.first_seen,
                    "last_seen": trace.last_seen,
                    "peak_population": trace.peak_population,
                    "extinct_tick": trace.extinct_tick,
                }
                for species_id, trace in engine.fossil.traces.items()
            },
            "events": [
                {"tick": event.tick, "kind": event.kind, "species": event.species_id,
                 "ancestor": event.ancestor, "detail": event.detail}
                for event in engine.fossil.events
            ],
        },
    }


def _engine_from_data(data: Dict[str, Any]) -> Engine:
    version = data.get("version")
    if version != SAVE_VERSION:
        raise ValueError(f"save version {version!r} is not {SAVE_VERSION}")
    engine = Engine(config=WorldConfig(**data["config"]), seed=int(data["seed"]), founders=0)
    layers = data["world"]
    engine.world.terrain = [int(tile) for tile in layers["terrain"]]
    engine.world.phase = [float(offset) for offset in layers["phase"]]
    engine.world.food = [float(stock) for stock in layers["food"]]
    engine.world.temperature = [float(heat) for heat in layers["temperature"]]
    engine.creatures = [_creature_from(row) for row in data["creatures"]]
    engine.registry = SpeciesRegistry.from_species(
        [_species_from(row) for row in data["species"]])
    engine.fossil = _fossil_from(data["fossil"])
    engine.tick = int(data["tick"])
    engine.next_cid = int(data["next_cid"])
    state = data["rng"]
    engine.rng.setstate((int(state["version"]), tuple(int(word) for word in state["state"]),
                         state["gauss_next"]))
    return engine


def _creature_from(row: Dict[str, Any]) -> Creature:
    genes = tuple(float(value) for value in row["genes"])
    return Creature(cid=int(row["cid"]), genome=Genome(genes=genes), x=int(row["x"]),
                    y=int(row["y"]), energy=float(row["energy"]), age=int(row["age"]),
                    alive=bool(row["alive"]), species=int(row["species"]))


def _species_from(row: Dict[str, Any]) -> Species:
    genes = tuple(float(value) for value in row["genes"])
    return Species(species_id=int(row["id"]), founder_genome=Genome(genes=genes),
                   birth_tick=int(row["birth_tick"]), ancestor=int(row["ancestor"]))


def _fossil_from(data: Dict[str, Any]) -> FossilRecord:
    record = FossilRecord(event_cap=int(data["event_cap"]))
    record.speciations = int(data["speciations"])
    record.extinctions = int(data["extinctions"])
    record.traces = {
        int(species_id): SpeciesTrace(
            species_id=int(species_id),
            first_seen=int(row["first_seen"]),
            last_seen=int(row["last_seen"]),
            peak_population=int(row["peak_population"]),
            extinct_tick=(None if row["extinct_tick"] is None else int(row["extinct_tick"])),
        )
        for species_id, row in data["traces"].items()
    }
    record.events = [
        FossilEvent(tick=int(row["tick"]), kind=str(row["kind"]),
                    species_id=int(row["species"]), ancestor=int(row["ancestor"]),
                    detail=str(row["detail"]))
        for row in data["events"]
    ]
    return record
