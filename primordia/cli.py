"""The command line: run a biosphere, resume one, report on it, or step it interactively.

Every command works on the same engine and the same save format; `run` seeds a fresh world,
`resume` continues a saved one in place, `stats` reports without stepping, `repl` opens an
interactive shell (step, species, fossil, hash, save) and `web` serves the observatory. Streams
are injected, errors carry a `Why:` and a `Fix:` line, and exit codes are 0 success, 1 failure
and 2 usage.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from typing import List, Optional, Sequence, TextIO

from primordia import __version__
from primordia.analytics import species_counts, trait_means
from primordia.engine import Engine
from primordia.save import SaveError, load_from, save_to
from primordia.world import WorldConfig

_REPL_HELP = ("commands: step [N], stats, species [N], fossil [N], hash, save PATH,"
              " help, quit")


def main(argv: Optional[Sequence[str]] = None, out: Optional[TextIO] = None,
         err: Optional[TextIO] = None, stdin: Optional[TextIO] = None) -> int:
    """Run one command; returns the exit code: 0 success, 1 failure, 2 usage."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    stdin = sys.stdin if stdin is None else stdin
    parser = _build_parser()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as exit_call:
        return int(exit_call.code or 0)
    try:
        if args.command == "run":
            return _run(args, out)
        if args.command == "resume":
            return _resume(args, out)
        if args.command == "stats":
            return _stats(args, out)
        if args.command == "repl":
            return _repl(args, out, stdin)
        if args.command == "web":
            return _web(args, out)
    except SaveError as error:
        print(error, file=err)
        return 1
    parser.print_usage(err)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m primordia",
        description="A zero-dependency evolution sandbox: seed a biosphere, run its clock,"
                    " watch it speciate.")
    parser.add_argument("--version", action="version", version=f"primordia {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="start a fresh biosphere and step it")
    run.add_argument("--seed", type=int, default=42, help="same seed, same history")
    run.add_argument("--ticks", type=int, default=200, help="ticks to run before reporting")
    run.add_argument("--founders", type=int, default=60, help="creatures placed at tick 0")
    run.add_argument("--width", type=int, default=36, help="world width in tiles")
    run.add_argument("--height", type=int, default=18, help="world height in tiles")
    run.add_argument("--save", metavar="PATH", help="write the run to this save file")

    resume = commands.add_parser("resume", help="continue a saved run")
    resume.add_argument("path", metavar="PATH", help="the save file to continue")
    resume.add_argument("--ticks", type=int, default=200, help="ticks to run before reporting")
    resume.add_argument("--save", metavar="PATH", help="write elsewhere instead of in place")

    stats = commands.add_parser("stats", help="report a saved run without stepping it")
    stats.add_argument("path", metavar="PATH")

    repl = commands.add_parser("repl", help="step and inspect a world interactively")
    repl.add_argument("path", metavar="PATH", nargs="?",
                      help="a save to open, or none for a fresh world")
    repl.add_argument("--seed", type=int, default=42, help="the seed of a fresh world")

    web = commands.add_parser("web", help="open the observatory: a local web view of a world")
    web.add_argument("path", metavar="PATH", nargs="?",
                     help="a save to open, or none for a fresh world")
    web.add_argument("--seed", type=int, default=42, help="the seed of a fresh world")
    web.add_argument("--ticks", type=int, default=0, help="ticks to run before opening")
    web.add_argument("--host", default="127.0.0.1", help="interface to bind")
    web.add_argument("--port", type=int, default=8000, help="port to bind (0 picks a free one)")
    return parser


def _run(args: argparse.Namespace, out: TextIO) -> int:
    config = WorldConfig(width=args.width, height=args.height)
    engine = Engine(config=config, seed=args.seed, founders=args.founders)
    _advance(engine, args.ticks)
    _report(engine, out)
    if args.save:
        save_to(engine, args.save)
        print(f"saved {args.save}", file=out)
    return 0


def _resume(args: argparse.Namespace, out: TextIO) -> int:
    engine = load_from(args.path)
    _advance(engine, args.ticks)
    _report(engine, out)
    target = args.save or args.path
    save_to(engine, target)
    print(f"saved {target}", file=out)
    return 0


def _stats(args: argparse.Namespace, out: TextIO) -> int:
    _report(load_from(args.path), out)
    return 0


def _web(args: argparse.Namespace, out: TextIO) -> int:
    from primordia.web import serve

    engine = load_from(args.path) if args.path else Engine(seed=args.seed)
    _advance(engine, args.ticks)
    return serve(engine, args.host, args.port,
                 out=lambda line: print(line, file=out, flush=True))


def _repl(args: argparse.Namespace, out: TextIO, stdin: TextIO) -> int:
    engine = load_from(args.path) if args.path else Engine(seed=args.seed)
    _report(engine, out)
    interactive = bool(getattr(stdin, "isatty", lambda: False)())
    while True:
        if interactive:
            print("primordia> ", end="", flush=True, file=out)
        raw = stdin.readline()
        if not raw:
            break
        words = raw.split()
        if not words:
            continue
        command, rest = words[0], words[1:]
        if command in ("quit", "exit"):
            break
        if command == "help":
            print(_REPL_HELP, file=out)
        elif command == "step":
            count = _count(rest, 1)
            if count is None:
                print("step takes a whole number of ticks", file=out)
                continue
            _advance(engine, count)
            print(_summary_line(engine), file=out)
        elif command == "stats":
            _report(engine, out)
        elif command == "hash":
            print(engine.snapshot_hash(), file=out)
        elif command == "save":
            if not rest:
                print("usage: save PATH", file=out)
                continue
            save_to(engine, rest[0])
            print(f"saved {rest[0]}", file=out)
        elif command == "species":
            _print_species(engine, _count(rest, 10) or 10, out)
        elif command == "fossil":
            _print_fossil(engine, _count(rest, 10) or 10, out)
        else:
            print(f"unknown command: {command} (try `help`)", file=out)
    return 0


def _advance(engine: Engine, ticks: int) -> None:
    for _ in range(max(0, ticks)):
        engine.step()


def _report(engine: Engine, out: TextIO) -> None:
    print(_summary_line(engine), file=out)
    print(_lineage_line(engine), file=out)
    print(_traits_line(engine), file=out)


def _summary_line(engine: Engine) -> str:
    alive = len(engine.creatures)
    total = len(engine.registry)
    living = len({creature.species for creature in engine.creatures})
    return (f"tick {engine.tick}  population {alive}  species {living} alive of {total}"
            f"  speciations {engine.fossil.speciations}"
            f"  extinctions {engine.fossil.extinctions}")


def _lineage_line(engine: Engine) -> str:
    counts = species_counts(engine.creatures)
    if not counts:
        return "no living lineages"
    species_id = max(counts, key=lambda key: (counts[key], -key))
    trace = engine.fossil.traces.get(species_id)
    peak = trace.peak_population if trace else counts[species_id]
    return f"top lineage: species {species_id} with {counts[species_id]} alive, peak {peak}"


def _traits_line(engine: Engine) -> str:
    means = trait_means(engine.creatures)
    head = ", ".join(f"{name} {means[name]:.2f}"
                     for name in ("size", "speed", "metabolism", "diet"))
    return f"mean traits: {head}"


def _print_species(engine: Engine, limit: int, out: TextIO) -> None:
    counts = species_counts(engine.creatures)
    rows = sorted(counts.items(), key=lambda row: (-row[1], row[0]))[:limit]
    if not rows:
        print("no living lineages", file=out)
        return
    for species_id, alive in rows:
        record = engine.registry.get(species_id)
        trace = engine.fossil.traces.get(species_id)
        peak = trace.peak_population if trace else alive
        ancestor = record.ancestor if record.ancestor else "-"
        print(f"species {species_id}: alive {alive}, peak {peak},"
              f" born tick {record.birth_tick}, ancestor {ancestor}", file=out)


def _print_fossil(engine: Engine, limit: int, out: TextIO) -> None:
    for event in engine.fossil.events[-limit:]:
        ancestor = event.ancestor if event.ancestor else "-"
        detail = f" {event.detail}" if event.detail else ""
        print(f"tick {event.tick}: {event.kind} of species {event.species_id}"
              f" (ancestor {ancestor}){detail}", file=out)


def _count(words: List[str], default: int) -> Optional[int]:
    if not words:
        return default
    try:
        value = int(words[0])
    except ValueError:
        return None
    return value if value >= 0 else None
