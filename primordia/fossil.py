"""The fossil record: species sightings, peaks, extinction episodes and a bounded event log.

The engine censuses the living population once per tick. `traces` keeps the whole story, one
row per species id; `events` is a bounded window over the latest moments, so memory never
grows with run length, and the speciation/extinction counters stay monotonic even when the
window forgets an old event. An absence from a census is one extinction episode: a species
that reappears later clears its extinction and can end again, so the counter counts moments,
not gravestones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

FOSSIL_EVENT_CAP = 10_000


@dataclass(frozen=True)
class FossilEvent:
    """One durable moment: a speciation or an extinction, with its tick and lineage ids."""

    tick: int
    kind: str
    species_id: int
    ancestor: int
    detail: str


@dataclass
class SpeciesTrace:
    """One lineage's sighting history, as censuses accumulate."""

    species_id: int
    first_seen: int
    last_seen: int
    peak_population: int = 0
    extinct_tick: Optional[int] = None


class FossilRecord:
    """Sightings and events per species; one census miss is one extinction episode."""

    def __init__(self, event_cap: int = FOSSIL_EVENT_CAP) -> None:
        self.event_cap = event_cap
        self.traces: Dict[int, SpeciesTrace] = {}
        self.events: List[FossilEvent] = []
        self.speciations = 0
        self.extinctions = 0

    def record_speciation(self, tick: int, species_id: int, ancestor: int,
                          detail: str = "") -> None:
        """Note a new lineage; the counter is monotonic even when the window forgets."""
        self.speciations += 1
        self._append(FossilEvent(tick=tick, kind="speciation", species_id=species_id,
                                 ancestor=ancestor, detail=detail))

    def census(self, counts: Mapping[int, int], tick: int) -> None:
        """Update sightings and peaks from one count per species; a census miss is an episode."""
        for species_id, count in sorted(counts.items()):
            trace = self.traces.get(species_id)
            if trace is None:
                self.traces[species_id] = SpeciesTrace(species_id=species_id, first_seen=tick,
                                                       last_seen=tick, peak_population=count)
                continue
            trace.last_seen = tick
            trace.peak_population = max(trace.peak_population, count)
            if trace.extinct_tick is not None:
                trace.extinct_tick = None
        for species_id, trace in sorted(self.traces.items()):
            if trace.extinct_tick is None and species_id not in counts:
                trace.extinct_tick = tick
                self.extinctions += 1
                self._append(FossilEvent(tick=tick, kind="extinction", species_id=species_id,
                                         ancestor=0, detail=""))

    def _append(self, event: FossilEvent) -> None:
        self.events.append(event)
        if len(self.events) > self.event_cap:
            del self.events[0]
