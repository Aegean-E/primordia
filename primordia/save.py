"""Persistence: one versioned JSON snapshot carries a whole run across processes.

A save holds everything the engine needs to replay its future exactly: the world's layers,
every creature, the species registry, the fossil record and the raw state of the engine's
`random.Random`. Writes are atomic - a temp file is flushed and fsynced, the previous save
rotates to `.bak`, and `os.replace` swaps the new file in with retries - so a crash leaves
either the old save or the new one, never half of either. A corrupt primary is quarantined and
the `.bak` takes over; when no usable file remains, `SaveError` says why and what to do.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Union

from primordia.creature import Creature
from primordia.engine import Engine
from primordia.fossil import FossilEvent, FossilRecord, SpeciesTrace
from primordia.genome import Genome
from primordia.species import SPECIATION_DISTANCE, Species, SpeciesRegistry
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


def dump_text(engine: Engine) -> str:
    """The engine's full state as the compact JSON text `save_to` writes."""
    return json.dumps(_engine_to_data(engine), separators=(",", ":"), allow_nan=False)


def save_to(engine: Engine, path: Union[str, Path]) -> Path:
    """Write the engine's full state to `path` atomically, rotating the old file to `.bak`."""
    path = Path(path)
    if path.is_dir():
        raise SaveError(
            f"could not write the save to {path}",
            why="that path is a folder, and a folder cannot be replaced by a file",
            fix="choose a file path inside the folder, for example `run.json`",
        )
    try:
        payload = dump_text(engine)
    except (TypeError, ValueError) as error:
        raise SaveError(
            f"could not write the save to {path}",
            why=f"the run holds a value that JSON cannot store ({error})",
            fix="remove the non-finite value or start a new run; the existing save is untouched",
        ) from error
    temp = path.with_name(path.name + f".tmp_{os.getpid()}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            _replace(path, Path(str(path) + BACKUP_SUFFIX))
        _replace(temp, path)
        _sync_directory(path.parent)
    except OSError as error:
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
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
        backup = Path(str(path) + BACKUP_SUFFIX)
        if backup.exists():
            try:
                engine = _engine_from_data(_read_json(backup))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError, SaveError):
                engine = None
            if engine is not None:
                save_to(engine, path)
                return engine
            raise SaveError(
                f"save not found: {path}",
                why=f"the primary file is missing and its backup at {backup} cannot be read",
                fix="start a new run with `python -m primordia run --save <path>`",
            )
        raise SaveError(
            f"save not found: {path}",
            why="no file exists at that path",
            fix="check the path, or start a new run with `python -m primordia run --save <path>`",
        )
    if path.is_dir():
        raise SaveError(
            f"could not read the save at {path}",
            why="that path is a folder, not a save file",
            fix="point at the save file itself, for example `<folder>/run.json`",
        )
    try:
        return _engine_from_data(_read_json(path))
    except OSError as error:
        raise SaveError(
            f"could not read the save at {path}",
            why=f"the file could not be opened or read ({error})",
            fix="check the path and its permissions, then try again",
        ) from error
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        try:
            wreck = _quarantine(path)
        except OSError as move_error:
            raise SaveError(
                f"could not read the save at {path}",
                why=f"the file is corrupt and could not be moved aside ({move_error})",
                fix="close whatever is using the file, or move it away yourself, then try again",
            ) from move_error
        backup = Path(str(path) + BACKUP_SUFFIX)
        if backup.exists():
            try:
                engine = _engine_from_data(_read_json(backup))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError, SaveError):
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
        "species_distance": engine.registry.distance,
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
    if not isinstance(data, dict) or "version" not in data:
        raise SaveError(
            "this file is not a primordia save",
            why="its JSON has no format version, so it was not written by primordia",
            fix="check that the path points at a primordia save, or start a new run",
        )
    version = data.get("version")
    if version != SAVE_VERSION:
        raise SaveError(
            f"this save is written in format version {version!r}; this build reads version "
            f"{SAVE_VERSION}",
            why="the save was written by a different (probably newer) primordia",
            fix="open it with the primordia that wrote it, or start a new run",
        )
    engine = Engine(config=WorldConfig(**data["config"]), seed=int(data["seed"]), founders=0)
    layers = data["world"]
    engine.world.terrain = [int(tile) for tile in layers["terrain"]]
    engine.world.phase = [float(offset) for offset in layers["phase"]]
    engine.world.food = [float(stock) for stock in layers["food"]]
    engine.world.temperature = [float(heat) for heat in layers["temperature"]]
    engine.creatures = [_creature_from(row) for row in data["creatures"]]
    engine.registry = SpeciesRegistry.from_species(
        [_species_from(row) for row in data["species"]],
        distance=float(data.get("species_distance", SPECIATION_DISTANCE)))
    engine.fossil = _fossil_from(data["fossil"])
    engine.tick = int(data["tick"])
    engine.next_cid = int(data["next_cid"])
    state = data["rng"]
    engine.rng.setstate((int(state["version"]), tuple(int(word) for word in state["state"]),
                         state["gauss_next"]))
    _verify_engine(engine)
    return engine


def _verify_engine(engine: Engine) -> None:
    """Reject a parseable but inconsistent snapshot before any tick can crash on it."""
    width, height = engine.config.width, engine.config.height
    length = width * height
    for name in ("terrain", "phase", "food", "temperature"):
        layer = getattr(engine.world, name)
        if len(layer) != length:
            raise ValueError(
                f"the {name} layer holds {len(layer)} tiles but the world needs {length}")
    if any(tile not in (0, 1) for tile in engine.world.terrain):
        raise ValueError("the terrain layer holds a value that is neither land nor water")
    if any(not math.isfinite(value) for value in engine.world.phase):
        raise ValueError("the season phase layer holds a non-finite value")
    if any(not math.isfinite(value) or value < 0.0 or value > engine.config.food_cap
           for value in engine.world.food):
        raise ValueError("the food layer holds a value outside [0, food_cap]")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0
           for value in engine.world.temperature):
        raise ValueError("the temperature layer holds a value outside [0, 1]")
    if not 0 <= engine.tick or engine.next_cid < 1:
        raise ValueError("the snapshot has a negative tick or a non-positive next cid")
    if not math.isfinite(engine.registry.distance) or engine.registry.distance < 0.0:
        raise ValueError("the species distance must be a non-negative finite number")
    seen = set()
    for creature in engine.creatures:
        if creature.cid in seen:
            raise ValueError(f"creature id {creature.cid} appears twice")
        seen.add(creature.cid)
        if not 1 <= creature.cid < engine.next_cid:
            raise ValueError(f"creature id {creature.cid} is not below next_cid {engine.next_cid}")
        if not (0 <= creature.x < width and 0 <= creature.y < height):
            raise ValueError(f"creature {creature.cid} is outside the {width}x{height} world")
        if not engine.world.is_land(creature.x, creature.y):
            raise ValueError(f"creature {creature.cid} stands on a water tile")
        if not math.isfinite(creature.energy) or creature.energy < 0.0:
            raise ValueError(f"creature {creature.cid} holds invalid energy")
        if not 0 <= creature.age <= engine.tick:
            raise ValueError(
                f"creature {creature.cid} has age {creature.age}, outside [0, {engine.tick}]")
        if not 1 <= creature.species <= len(engine.registry):
            raise ValueError(
                f"creature {creature.cid} names species {creature.species}, which is not recorded")
    for index in range(1, len(engine.registry) + 1):
        record = engine.registry.get(index)
        if record.species_id != index:
            raise ValueError(f"species row {index} carries id {record.species_id}")
        if not 0 <= record.birth_tick <= engine.tick:
            raise ValueError(f"species {index} has an impossible birth tick")
        if not 0 <= record.ancestor < index:
            raise ValueError(f"species {index} names an impossible ancestor")
    _verify_fossil(engine.fossil, len(engine.registry), engine.tick)


def _verify_fossil(fossil: FossilRecord, species_total: int, tick: int) -> None:
    """Keep traces and events inside the registry, the run and the declared event window."""
    if fossil.event_cap < 0 or len(fossil.events) > fossil.event_cap:
        raise ValueError("the fossil event log exceeds its declared capacity")
    if fossil.speciations < 0 or fossil.extinctions < 0:
        raise ValueError("the fossil counters cannot be negative")
    for species_id, trace in fossil.traces.items():
        if not 1 <= species_id <= species_total:
            raise ValueError(f"the fossil record traces unknown species {species_id}")
        if trace.species_id != species_id:
            raise ValueError(f"fossil trace {species_id} carries a different id")
        if min(trace.first_seen, trace.last_seen, trace.peak_population) < 0:
            raise ValueError(f"fossil trace {species_id} holds a negative measure")
        if trace.first_seen > trace.last_seen or trace.last_seen > tick:
            raise ValueError(f"fossil trace {species_id} holds an impossible sighting window")
        if trace.extinct_tick is not None and trace.extinct_tick > tick:
            raise ValueError(f"fossil trace {species_id} went extinct after the snapshot's tick")
    for event in fossil.events:
        if not 1 <= event.species_id <= species_total:
            raise ValueError(f"fossil event names unknown species {event.species_id}")
        if event.kind not in ("speciation", "extinction"):
            raise ValueError(f"fossil event has unknown kind {event.kind!r}")
        if not 0 <= event.tick <= tick:
            raise ValueError("fossil event has a tick outside the run")
        if not 0 <= event.ancestor < event.species_id:
            raise ValueError(f"fossil event names an impossible ancestor {event.ancestor}")


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
