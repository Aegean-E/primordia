"""Unit tests for the command line: run, resume, stats and the interactive shell."""

import io
import tempfile
import unittest
from pathlib import Path

from primordia.cli import main
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
