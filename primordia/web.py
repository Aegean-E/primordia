"""The observatory: a local web view of a running world, with god-mode interventions.

`serve` puts one engine behind a small stdlib HTTP server: the dashboard renders the map, the
population, the species table and the fossil record; `?step=N` advances the clock before
rendering and `?step=N&auto=S` adds a meta refresh so a tab can watch itself. The god-mode
forms (meteor, bloom, cull, introduce) post into `shocks`, `/state.json` serves the same facts
as data and `/save` downloads the standard save file. Everything is server-rendered HTML - no
script assets, no third-party requests, works offline.
"""

from __future__ import annotations

import html
import http.server
import json
import threading
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

from primordia import shocks
from primordia.analytics import species_counts, trait_means
from primordia.engine import Engine
from primordia.save import SaveError, dump_text
from primordia.world import LAND

MAX_STEP_PER_REQUEST = 2000
MAX_POST_BYTES = 4096
RECENT_EVENTS = 20
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

_STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: #0b0f14; color: #d7e0ea;
       font: 14px/1.5 ui-monospace, Menlo, Consolas, monospace; }
h1 { margin: 0 0 4px; font-size: 22px; }
h1 .sub { color: #6f8296; font-size: 14px; }
h2 { margin: 18px 0 6px; font-size: 15px; color: #9fd0a8; }
a { color: #7fc7ff; text-decoration: none; margin-right: 12px; }
a:hover { text-decoration: underline; }
.stats { margin: 2px 0; }
.traits { margin: 2px 0; color: #93a5b8; }
.notice { background: #1c2a1e; border: 1px solid #2f6b3a; padding: 6px 10px; border-radius: 6px; }
.layout { display: flex; gap: 24px; align-items: flex-start; margin-top: 14px; }
.map { display: grid; gap: 1px; background: #1a2430; padding: 1px; border-radius: 6px; }
.tile { width: 16px; height: 16px; position: relative; }
.dot { position: absolute; left: 3px; top: 3px; width: 10px; height: 10px; border-radius: 50%;
       box-shadow: 0 0 4px rgba(255, 255, 255, 0.35); }
aside { min-width: 360px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: right; padding: 2px 8px; border-bottom: 1px solid #1a2430; }
th:first-child, td:first-child { text-align: left; }
form { margin: 4px 0 10px; }
input, button { background: #121a23; color: #d7e0ea; border: 1px solid #2a3a4a;
                border-radius: 4px; padding: 3px 6px; font: inherit; }
input { width: 64px; }
button { cursor: pointer; }
button:hover { background: #1d2a38; }
ol { padding-left: 20px; margin: 4px 0; }
li { color: #b9c6d4; }
"""


def state_payload(engine: Engine) -> Dict[str, Any]:
    """The observable facts of one world, as JSON-ready data."""
    counts = species_counts(engine.creatures)
    rows = []
    for species_id in sorted(counts):
        record = engine.registry.get(species_id)
        trace = engine.fossil.traces.get(species_id)
        rows.append({
            "id": species_id,
            "alive": counts[species_id],
            "peak": trace.peak_population if trace else counts[species_id],
            "birth_tick": record.birth_tick,
            "ancestor": record.ancestor,
        })
    return {
        "tick": engine.tick,
        "population": len(engine.creatures),
        "species_total": len(engine.registry),
        "species_alive": len(rows),
        "speciations": engine.fossil.speciations,
        "extinctions": engine.fossil.extinctions,
        "traits": {name: round(value, 3) for name, value in trait_means(engine.creatures).items()},
        "width": engine.config.width,
        "height": engine.config.height,
        "terrain": list(engine.world.terrain),
        "food": [round(stock, 2) for stock in engine.world.food],
        "creatures": [[creature.x, creature.y, creature.species] for creature in engine.creatures],
        "species": rows,
        "events": [
            {"tick": event.tick, "kind": event.kind, "species": event.species_id,
             "ancestor": event.ancestor, "detail": event.detail}
            for event in engine.fossil.events[-100:]
        ],
    }


def render_dashboard(engine: Engine, auto: int = 0, notice: str = "") -> str:
    """The whole dashboard as one self-contained HTML page."""
    payload = state_payload(engine)
    width, height = payload["width"], payload["height"]
    cx, cy = width // 2, height // 2
    meta = f'<meta http-equiv="refresh" content="{auto}">' if auto > 0 else ""
    notice_html = f'<p class="notice">{html.escape(notice)}</p>' if notice else ""
    traits = ", ".join(f"{name} {value:.2f}" for name, value in payload["traits"].items())
    rows_html = "".join(
        f"<tr><td>{row['id']}</td><td>{row['alive']}</td><td>{row['peak']}</td>"
        f"<td>{row['birth_tick']}</td><td>{row['ancestor'] or '-'}</td></tr>"
        for row in sorted(payload["species"], key=lambda row: (-row["alive"], row["id"])))
    events_html = "".join(
        f"<li>tick {event['tick']}: {html.escape(str(event['kind']))} of species"
        f" {event['species']} (ancestor {event['ancestor'] or '-'})"
        f"{html.escape(' ' + event['detail']) if event['detail'] else ''}</li>"
        for event in reversed(payload["events"][-RECENT_EVENTS:]))
    god_html = _god_forms(cx, cy, width, height)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">{meta}
<title>Primordia observatory</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>Primordia <span class="sub">tick {payload['tick']}</span></h1>
<p class="stats">population {payload['population']} &middot; species {payload['species_alive']} alive of {payload['species_total']} &middot; speciations {payload['speciations']} &middot; extinctions {payload['extinctions']}</p>
<p class="traits">mean traits: {traits}</p>
<nav><a href="/?step=1">step 1</a><a href="/?step=25">step 25</a><a href="/?step=100">step 100</a><a href="/?step=400&auto=2">auto-play</a><a href="/">refresh</a><a href="/state.json">state.json</a><a href="/save">save</a></nav>
{notice_html}
<div class="layout">
<section class="map" style="grid-template-columns: repeat({width}, 16px)">{_map_html(engine, payload)}</section>
<aside>
{god_html}
<h2>Species</h2>
<table><tr><th>id</th><th>alive</th><th>peak</th><th>born</th><th>ancestor</th></tr>{rows_html}</table>
<h2>Fossil record</h2>
<ol>{events_html}</ol>
</aside>
</div>
</body>
</html>
"""


def _map_html(engine: Engine, payload: Dict[str, Any]) -> str:
    """The tile grid: food shaded green, water blue, creatures dotted by lineage colour."""
    cap = max(engine.world.config.food_cap, 1e-9)
    occupied: Dict[int, List[int]] = {}
    for x, y, species_id in payload["creatures"]:
        occupied.setdefault(y * payload["width"] + x, []).append(species_id)
    tiles = []
    for index, terrain in enumerate(payload["terrain"]):
        x, y = engine.world.xy(index)
        if terrain == LAND:
            fraction = min(1.0, payload["food"][index] / cap)
            background = f"rgb(20,{int(45 + 120 * fraction)},{int(30 + 40 * fraction)})"
            title = f"({x}, {y}) food {payload['food'][index]:.2f}"
        else:
            background = "rgb(16,32,54)"
            title = f"({x}, {y}) water"
        dots = "".join(
            f'<span class="dot" style="background:hsl({(species_id * 137) % 360}, 80%, 60%)">'
            f"</span>"
            for species_id in occupied.get(index, ()))
        tiles.append(f'<div class="tile" style="background:{background}" title="{title}">{dots}'
                     f"</div>")
    return "".join(tiles)


def _god_forms(cx: int, cy: int, width: int, height: int) -> str:
    """The intervention forms, pre-filled with the world's centre."""
    spot = (f'<input name="x" type="number" value="{cx}" min="0" max="{width - 1}">'
            f'<input name="y" type="number" value="{cy}" min="0" max="{height - 1}">')
    return f"""<h2>God mode</h2>
<form method="post" action="/god/meteor">{spot}<input name="radius" type="number" value="2" min="1" max="{shocks.MAX_RADIUS}"><button>meteor</button></form>
<form method="post" action="/god/bloom">{spot}<input name="radius" type="number" value="1" min="1" max="{shocks.MAX_RADIUS}"><button>bloom</button></form>
<form method="post" action="/god/cull"><input name="share" type="number" value="0.25" min="0" max="1" step="0.05"><button>cull the weakest</button></form>
<form method="post" action="/god/introduce"><input name="count" type="number" value="10" min="1" max="{shocks.MAX_INTRODUCTION}"><button>introduce near-clones</button></form>"""


def make_handler(engine: Engine, lock: threading.Lock, quiet: bool = False) -> type:
    """The HTTP handler bound to one engine; every engine touch happens under `lock`."""

    class Observatory(http.server.BaseHTTPRequestHandler):
        server_version = "PrimordiaObservatory/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            if not quiet:
                super().log_message(fmt, *args)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/":
                try:
                    step = _query_int(query, "step", 0, 0, MAX_STEP_PER_REQUEST)
                    auto = _query_int(query, "auto", 0, 0, 3600)
                except ValueError as error:
                    self._send_page(400, _error_page(str(error)))
                    return
                with lock:
                    for _ in range(step):
                        engine.step()
                    notice = query.get("notice", [""])[0]
                    self._send_page(200, render_dashboard(engine, auto=auto, notice=notice))
            elif parsed.path == "/state.json":
                with lock:
                    body = json.dumps(state_payload(engine),
                                      separators=(",", ":")).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            elif parsed.path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            elif parsed.path == "/save":
                with lock:
                    body = dump_text(engine).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8",
                               extra={"Content-Disposition":
                                      f'attachment; filename="primordia-{engine.tick}.json"'})
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                length = _content_length(self.headers.get("Content-Length"))
                fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            except ValueError as error:
                self.close_connection = True
                self._send_page(400, _error_page(str(error)))
                return
            with lock:
                try:
                    report = _apply_god(engine, parsed.path, fields)
                except ValueError as error:
                    self._send_page(400, _error_page(str(error)))
                    return
            summary = f"{report.action}: {report.detail} ({report.tiles} tiles, {report.creatures} creatures)"
            self.send_response(303)
            self.send_header("Location", "/?notice=" + urllib.parse.quote(summary))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send(self, status: int, body: bytes, content_type: str,
                  extra: Optional[Dict[str, str]] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_page(self, status: int, page: str) -> None:
            self._send(status, page.encode("utf-8"), "text/html; charset=utf-8")

    return Observatory


def make_server(engine: Engine, host: str = "127.0.0.1", port: int = 8000,
                quiet: bool = False) -> http.server.ThreadingHTTPServer:
    """A server for `engine` on `(host, port)`; port 0 picks a free one."""
    handler = make_handler(engine, threading.Lock(), quiet=quiet)
    return http.server.ThreadingHTTPServer((host, port), handler)


def serve(engine: Engine, host: str = "127.0.0.1", port: int = 8000,
          out: Optional[Callable[[str], None]] = None) -> int:
    """Run the observatory until interrupted; returns the exit code 0."""
    emit = print if out is None else out
    try:
        server = make_server(engine, host, port)
    except (OSError, OverflowError) as error:
        raise SaveError(
            f"could not open the observatory on {host}:{port}",
            why=f"the operating system refused that address ({error})",
            fix="choose another port, for example --port 8001, or let the system pick"
                " a free one with --port 0",
        ) from error
    bound_host, bound_port = server.server_address[:2]
    emit(f"observatory at http://{bound_host}:{bound_port} (ctrl-c stops)")
    if str(bound_host).lower() not in LOOPBACK_HOSTS:
        emit("warning: the observatory has no authentication; anyone who can reach"
             " this address can step the world and fire god-mode shocks")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _apply_god(engine: Engine, path: str, fields: Dict[str, List[str]]) -> shocks.ShockReport:
    """Map one god-mode POST path onto a shock; bad input raises ValueError."""
    if path == "/god/meteor":
        return shocks.meteor(engine, _field_int(fields, "x"), _field_int(fields, "y"),
                             _field_int(fields, "radius"))
    if path == "/god/bloom":
        return shocks.bloom(engine, _field_int(fields, "x"), _field_int(fields, "y"),
                            _field_int(fields, "radius"),
                            share=_field_float(fields, "share", default=1.0))
    if path == "/god/cull":
        return shocks.cull(engine, _field_float(fields, "share"))
    if path == "/god/introduce":
        return shocks.introduce(engine, _field_int(fields, "count"))
    raise ValueError(f"unknown intervention: {path}")


def _content_length(header: Optional[str]) -> int:
    """Validate the declared body size before reading; a bad header is a 400, never a wait."""
    if not header:
        return 0
    try:
        length = int(header)
    except ValueError:
        raise ValueError("Content-Length must be a whole number") from None
    if length < 0:
        raise ValueError("Content-Length cannot be negative")
    if length > MAX_POST_BYTES:
        raise ValueError(f"the form body must be at most {MAX_POST_BYTES} bytes")
    return length


def _query_int(query: Dict[str, List[str]], name: str, default: int, low: int, high: int) -> int:
    values = query.get(name)
    if not values:
        return default
    try:
        value = int(values[0])
    except ValueError:
        raise ValueError(f"{name} must be a whole number") from None
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _field_int(fields: Dict[str, List[str]], name: str) -> int:
    values = fields.get(name)
    if not values:
        raise ValueError(f"the form needs {name}")
    try:
        return int(values[0])
    except ValueError:
        raise ValueError(f"{name} must be a whole number") from None


def _field_float(fields: Dict[str, List[str]], name: str,
                 default: Optional[float] = None) -> float:
    values = fields.get(name)
    if not values:
        if default is None:
            raise ValueError(f"the form needs {name}")
        return default
    try:
        return float(values[0])
    except ValueError:
        raise ValueError(f"{name} must be a number") from None


def _error_page(message: str) -> str:
    """A refusal page that names what was rejected and how to fix the request."""
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f"<title>Primordia: refused</title></head><body>"
            f"<h1>Refused</h1><p>Why: {html.escape(message)}</p>"
            f"<p>Fix: send whole numbers inside the shown bounds and try again.</p>"
            f'<p><a href="/">back to the observatory</a></p></body></html>')
