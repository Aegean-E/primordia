"""Unit tests for the command line: run, resume, stats and the interactive shell."""

import io
import tempfile
import unittest
from pathlib import Path

from primordia import __version__
from primordia.cli import _persist_session, main
from primordia.save import load_from


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "run.json")

    def run_cli(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        code = main(argv, out=out, err=err, stdin=io.StringIO(stdin))
        return code, out.getvalue(), err.getvalue()

    def test_run_reports_a_summary_and_writes_a_save(self):
        code, out, err = self.run_cli(["run", "--seed", "5", "--ticks", "40",
                                       "--save", self.path])
        self.assertEqual(code, 0, err)
        self.assertIn("population", out)
        self.assertEqual(load_from(self.path).tick, 40)

    def test_resume_continues_the_saved_history(self):
        self.run_cli(["run", "--seed", "5", "--ticks", "20", "--save", self.path])
        code, out, err = self.run_cli(["resume", self.path, "--ticks", "20"])
        self.assertEqual(code, 0, err)
        self.assertEqual(load_from(self.path).tick, 40)

    def test_stats_prints_population_species_and_fossil_counters(self):
        self.run_cli(["run", "--seed", "4", "--ticks", "80", "--save", self.path])
        code, out, err = self.run_cli(["stats", self.path])
        self.assertEqual(code, 0, err)
        for token in ("tick", "population", "species", "speciations"):
            self.assertIn(token, out)

    def test_missing_save_exits_one_with_why_and_fix(self):
        code, out, err = self.run_cli(["stats", str(Path(self.temp.name) / "nope.json")])
        self.assertEqual(code, 1)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)

    def test_usage_errors_exit_two(self):
        code, out, err = self.run_cli(["run", "--ticks", "many"])
        self.assertEqual(code, 2)

    def test_an_impossible_world_exits_two_with_a_fix(self):
        code, out, err = self.run_cli(["run", "--width", "0", "--ticks", "1"])
        self.assertEqual(code, 2)
        self.assertIn("Fix:", err)

    def test_version_flag_prints_the_version(self):
        code, out, err = self.run_cli(["--version"])
        self.assertEqual(code, 0, err)
        self.assertIn(__version__, out)

    def test_repl_steps_stats_hashes_saves_and_quits(self):
        script = "step 10\nstats\nhash\nsave {}\nquit\n".format(self.path)
        code, out, err = self.run_cli(["repl", "--seed", "5"], stdin=script)
        self.assertEqual(code, 0, err)
        self.assertIn("tick 10", out)
        self.assertEqual(load_from(self.path).tick, 10)

    def test_repl_survives_unknown_commands(self):
        code, out, err = self.run_cli(["repl", "--seed", "5"], stdin="frobnicate\nquit\n")
        self.assertEqual(code, 0)
        self.assertIn("unknown", out.lower())

    def test_repl_refuses_zero_row_listings(self):
        code, out, err = self.run_cli(["repl", "--seed", "5"],
                                      stdin="species 0\nfossil 0\nquit\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count("positive whole number"), 2)

    def test_the_observatory_persists_session_changes_back_to_its_save(self):
        self.run_cli(["run", "--seed", "5", "--ticks", "20", "--save", self.path])
        engine = load_from(self.path)
        start = engine.snapshot_hash()
        for _ in range(5):
            engine.step()
        out = io.StringIO()
        self.assertTrue(_persist_session(engine, self.path, start, out))
        self.assertIn("saved", out.getvalue())
        self.assertEqual(load_from(self.path).tick, 25)

    def test_an_untouched_observatory_leaves_its_save_alone(self):
        self.run_cli(["run", "--seed", "5", "--ticks", "20", "--save", self.path])
        before = Path(self.path).stat().st_mtime_ns
        engine = load_from(self.path)
        out = io.StringIO()
        self.assertFalse(_persist_session(engine, self.path, engine.snapshot_hash(), out))
        self.assertEqual(Path(self.path).stat().st_mtime_ns, before)
