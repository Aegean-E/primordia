"""Unit tests for the fossil record: sightings, peaks, extinctions and the event log."""

import unittest

from primordia.fossil import FossilRecord


class CensusTests(unittest.TestCase):
    def test_census_records_first_last_and_peak(self):
        fossil = FossilRecord()
        fossil.census({1: 4, 2: 1}, tick=0)
        fossil.census({1: 7}, tick=1)
        fossil.census({1: 3, 2: 2}, tick=2)
        first = fossil.traces[1]
        self.assertEqual(first.first_seen, 0)
        self.assertEqual(first.last_seen, 2)
        self.assertEqual(first.peak_population, 7)
        second = fossil.traces[2]
        self.assertEqual(second.first_seen, 0)
        self.assertEqual(second.last_seen, 2)
        self.assertEqual(second.peak_population, 2)

    def test_extinction_when_a_species_leaves_the_census(self):
        fossil = FossilRecord()
        fossil.census({1: 2, 2: 2}, tick=0)
        fossil.census({1: 2}, tick=5)
        self.assertEqual(fossil.traces[2].extinct_tick, 5)
        self.assertEqual(fossil.extinctions, 1)
        events = [event for event in fossil.events if event.kind == "extinction"]
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].tick, events[0].species_id), (5, 2))

    def test_extinct_species_can_reappear_without_a_new_speciation(self):
        fossil = FossilRecord()
        fossil.census({1: 1}, tick=0)
        fossil.census({}, tick=1)
        fossil.census({1: 1}, tick=2)
        self.assertIsNone(fossil.traces[1].extinct_tick)
        self.assertEqual(fossil.extinctions, 1)

    def test_event_log_is_bounded_and_counters_stay_monotonic(self):
        fossil = FossilRecord(event_cap=3)
        for species_id in range(1, 8):
            fossil.record_speciation(tick=species_id, species_id=species_id, ancestor=species_id - 1)
        self.assertEqual(len(fossil.events), 3)
        self.assertEqual(fossil.speciations, 7)
