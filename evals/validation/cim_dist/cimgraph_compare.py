#!/usr/bin/env python3
"""Leg C of the distribution CIM validation: CIM-Graph structural
comparison, in three directions.

- C1, the source read by both: per table, the mRIDs CIM-Graph finds for the
  table's classes equal the `cim_mrid`s PowerIO carries, less the objects
  PowerIO reports dropping; and each piece of equipment PowerIO carries
  connects to the same ConnectivityNodes in both, terminal by terminal.
- C2, PowerIO's fresh `cim-dist` output read by CIM-Graph: it loads, every
  reference resolves, the mRIDs PowerIO read come back unchanged, and the
  counts per table equal PowerIO's.
- C3, CIM-Graph's re-serialisation of the source (`cimgraph.utils.write_xml`)
  read by PowerIO: the network equals PowerIO's direct read of the source,
  table by table and field by field. This tests PowerIO against a second
  serializer: `rdf:about` with `urn:uuid:`, alphabetical class order, and
  associations stated from whichever end CIM-Graph keeps.

Each runs under two CIM-Graph profiles, `rc4_2021` (the GridAPPS-D CIM100
profile) and `cim17v40`, since each loses different data: `rc4_2021` has no
`Asset.PowerSystemResources`, and `cim17v40` spells `PhotoVoltaicUnit`.

CIM-Graph reads its profile from the environment at import, so it runs in a
subprocess per document and profile (`--worker`). Its parser logs a
document it cannot parse as "not found. Skipping." and carries on with an
empty graph; the worker reports that, and an empty graph, as fatal. Every
other CIM-Graph warning is counted by message and recorded, because the
sources themselves raise some (properties outside the profile).

Every case's counts are compared with `cimgraph_expected.json`.
`--update-expected` rewrites that file from the current run; review its diff
before committing it.

    python evals/validation/cim_dist/cimgraph_compare.py \
        --powerio target/release/powerio \
        [--corpus tests/data/large/cim_dist] [--report cimgraph.md]

Run it from the repository root in the `.venv-cim` environment
(`requirements-cim.txt`); `run_cim_dist_validation.sh` does both.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

EXPECTED = common.HERE / "cimgraph_expected.json"
PROFILES = ["rc4_2021", "cim17v40"]

SWITCH_CLASSES = [
    "Switch",
    "LoadBreakSwitch",
    "Breaker",
    "Recloser",
    "Sectionaliser",
    "Fuse",
    "Disconnector",
    "Jumper",
]
# The tables compared by identity and the source classes each comes from.
# Transformers are a tank each, or a PowerTransformer that owns no tank.
TABLE_CLASSES = {
    "buses": ["ConnectivityNode"],
    "lines": ["ACLineSegment"],
    "loads": ["EnergyConsumer"],
    "shunts": ["LinearShuntCompensator"],
    "sources": ["EnergySource"],
    "switches": SWITCH_CLASSES,
}
TABLES = [*TABLE_CLASSES, "transformers"]
# Equipment whose terminals C1 compares, and the field naming its bus.
EQUIPMENT = ["lines", "switches", "loads", "shunts", "sources", "transformers"]
# How C3 keys the records of each table.
RECORD_KEY = {"buses": "id"}
REL_TOL = 1e-9

# The cim-dist writer's drops of one record, by the noun its message opens
# with (EMIT_CIM_DIST_RECORD_DROPPED in powerio-dist/src/cim/write.rs).
EMIT_DROPPED = re.compile(r"EMIT\.CIM_DIST\.RECORD_DROPPED: (\w+) ")
DROP_SUBJECT = {"line": "lines", "load": "loads", "transformer": "transformers"}

FATAL = re.compile(r"not found\. Skipping|No files could be parsed|No root element")
# The parts of a CIM-Graph log message that name one object, replaced so
# messages count by kind.
ID_LIKE = re.compile(
    r"(urn:uuid:)?[#_]?[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}"
    # identifiers that are not UUIDs, in the messages that name one
    r"|(?<=^URI )\S+(?= not a valid UUID)"
    r"|(?<=^Object with ID )\S+(?= not found)"
    r"|\b\d+\b"
)


# ---------------------------------------------------------------------------
# The CIM-Graph worker (runs in .venv-cim, one profile per process)
# ---------------------------------------------------------------------------


def worker(source: Path, out: Path, write: Path | None) -> int:
    records: list[logging.LogRecord] = []

    class Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    root = logging.getLogger()
    root.addHandler(Grab(level=logging.WARNING))
    root.setLevel(logging.WARNING)

    from cimgraph.databases import XMLFile
    from cimgraph.models import FeederModel
    from cimgraph.utils import write_xml

    conn = XMLFile(filename=str(source))
    net = FeederModel(container=conn.cim.Feeder(), connection=conn, distributed=False)

    # An identifier that is not a UUID gets a UUID CIM-Graph derives from it,
    # and `uri()` returns that; the graph keeps the source's identifier as
    # the key, so identify objects, and the objects they reference, by it.
    key_of = {id(o): str(k) for objects in net.graph.values() for k, o in objects.items()}

    def ident(obj) -> str:
        return common.mrid(key_of.get(id(obj), obj.uri()))

    classes: dict[str, list[str]] = {}
    for cls, objects in net.graph.items():
        classes[cls.__name__] = sorted(ident(o) for o in objects.values())
    terminals = []
    for t in net.graph.get(conn.cim.Terminal, {}).values():
        ce, cn = getattr(t, "ConductingEquipment", None), getattr(t, "ConnectivityNode", None)
        if ce is not None and cn is not None:
            terminals.append([ident(ce), ident(cn)])
    tank_owner = {}
    for tank in net.graph.get(getattr(conn.cim, "TransformerTank", None), {}).values():
        owner = getattr(tank, "PowerTransformer", None)
        if owner is not None:
            tank_owner[ident(tank)] = ident(owner)
    if write is not None:
        write_xml(net, str(write))

    logs: Counter[str] = Counter()
    fatal = []
    for record in records:
        message = record.getMessage()
        if FATAL.search(message):
            fatal.append(message)
        logs[ID_LIKE.sub("<id>", message)] += 1
    if not any(classes.values()):
        fatal.append("CIM-Graph built an empty graph")
    out.write_text(
        json.dumps(
            {
                "fatal": fatal,
                "classes": classes,
                "terminals": terminals,
                "tank_owner": tank_owner,
                "logs": dict(logs),
            }
        ),
        encoding="utf-8",
    )
    return 0


def run_worker(profile: str, source: Path, work: Path, write: Path | None = None) -> dict:
    out = work / f"{source.name}.{profile}.cimgraph.json"
    env = dict(os.environ, CIMG_CIM_PROFILE=profile)
    args = [sys.executable, str(Path(__file__).resolve()), "--worker", str(source), str(out)]
    if write is not None:
        args.append(str(write))
    done = subprocess.run(args, check=False, capture_output=True, text=True, env=env)
    if done.returncode != 0 or not out.exists():
        tail = (done.stderr or "").strip().splitlines()[-1:] or [f"exit {done.returncode}"]
        return {
            "fatal": [f"worker failed: {tail[0]}"],
            "classes": {},
            "terminals": [],
            "tank_owner": {},
            "logs": {},
        }
    return json.loads(out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# What each side carries
# ---------------------------------------------------------------------------


def cimgraph_ids(graph: dict) -> dict[str, set[str]]:
    """Per table, the mRIDs CIM-Graph found for the table's classes."""
    classes = {k: set(v) for k, v in graph["classes"].items()}
    ids = {
        t: set().union(*(classes.get(c, set()) for c in cims)) for t, cims in TABLE_CLASSES.items()
    }
    owners = set(graph["tank_owner"].values())
    ids["transformers"] = classes.get("TransformerTank", set()) | (
        classes.get("PowerTransformer", set()) - owners
    )
    return ids


def powerio_ids(tables: dict) -> dict[str, set[str]]:
    return {
        t: {
            common.mrid(r["extras"]["cim_mrid"])
            for r in tables.get(t) or []
            if "cim_mrid" in (r.get("extras") or {})
        }
        for t in TABLES
    }


def powerio_dropped(doc: dict) -> set[str]:
    return {
        common.mrid(d["details"]["mrid"])
        for d in doc.get("diagnostics", [])
        if d["code"].endswith(".RECORD_DROPPED") and "mrid" in (d.get("details") or {})
    }


def powerio_edges(tables: dict) -> set[tuple[str, str]]:
    """(equipment, ConnectivityNode) for each terminal PowerIO carries. A
    tank's terminals belong to its PowerTransformer, as in CIM."""
    bus_mrid = {
        b["id"]: common.mrid(b["extras"]["cim_mrid"])
        for b in tables.get("buses") or []
        if "cim_mrid" in (b.get("extras") or {})
    }
    edges = set()
    for table in EQUIPMENT:
        for r in tables.get(table) or []:
            extras = r.get("extras") or {}
            owner = extras.get("cim_power_transformer") or extras.get("cim_mrid")
            if owner is None:
                continue
            if table == "transformers":
                buses = [w["bus"] for w in r["windings"]]
            elif "bus" in r:
                buses = [r["bus"]]
            else:
                buses = [r["bus_from"], r["bus_to"]]
            for bus in buses:
                if bus in bus_mrid:
                    edges.add((common.mrid(owner), bus_mrid[bus]))
    return edges


# ---------------------------------------------------------------------------
# The three directions
# ---------------------------------------------------------------------------


def c1(graph: dict, doc: dict, got: Counter[str]) -> None:
    cg = cimgraph_ids(graph)
    pio = powerio_ids(common.network(doc))
    dropped = powerio_dropped(doc)
    for table in TABLES:
        missing = cg[table] - pio[table] - dropped
        extra = pio[table] - cg[table]
        if missing:
            got[f"C1.MISSING {table}"] = len(missing)
        if extra:
            got[f"C1.EXTRA {table}"] = len(extra)
    carried = set().union(*(pio[t] for t in EQUIPMENT))
    carried |= {
        common.mrid(r["extras"]["cim_power_transformer"])
        for r in common.network(doc).get("transformers") or []
        if "cim_power_transformer" in (r.get("extras") or {})
    }
    cg_edges = {(e, n) for e, n in graph["terminals"] if e in carried}
    pio_edges = powerio_edges(common.network(doc))
    if cg_edges - pio_edges:
        got["C1.EDGE_MISSING"] = len(cg_edges - pio_edges)
    if pio_edges - cg_edges:
        got["C1.EDGE_EXTRA"] = len(pio_edges - cg_edges)


def emit_dropped(log: list[str]) -> Counter[str]:
    """Per table, the records the cim-dist writer reported not writing."""
    dropped: Counter[str] = Counter()
    for line in log:
        match = EMIT_DROPPED.match(line)
        if match and match.group(1) in DROP_SUBJECT:
            dropped[DROP_SUBJECT[match.group(1)]] += 1
    return dropped


def c2(graph: dict, doc: dict, source_doc: dict | None, log: list[str], got: Counter[str]) -> None:
    """`doc` is the IR PowerIO wrote the output from; `source_doc` the IR of
    the CIM source it came from, when there is one; `log` the writer's
    diagnostics."""
    cg = cimgraph_ids(graph)
    tables = common.network(doc)
    written = emit_dropped(log)
    for table in TABLES:
        gap = len(cg[table]) - (len(tables.get(table) or []) - written[table])
        if gap:
            got[f"C2.COUNT {table}"] = gap
    if source_doc is not None:
        read = powerio_ids(common.network(source_doc))
        for table in TABLES:
            changed = read[table] - cg[table]
            if changed:
                got[f"C2.MRID_CHANGED {table}"] = len(changed)


def same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=REL_TOL)
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def c3(direct: dict, reread: dict | None, got: Counter[str]) -> None:
    if reread is None:
        got["C3.UNPARSED"] = 1
        return
    a, b = common.network(direct), common.network(reread)
    for table in sorted(set(a) | set(b)):
        x, y = a.get(table), b.get(table)
        if not isinstance(x, list) or not isinstance(y, list):
            if not same(x, y):
                got[f"C3.FIELD {table}"] += 1
            continue
        key = RECORD_KEY.get(table, "name")
        xa = {r.get(key): r for r in x}
        ya = {r.get(key): r for r in y}
        if xa.keys() - ya.keys():
            got[f"C3.MISSING {table}"] = len(xa.keys() - ya.keys())
        if ya.keys() - xa.keys():
            got[f"C3.EXTRA {table}"] = len(ya.keys() - xa.keys())
        for k in xa.keys() & ya.keys():
            for field in sorted(set(xa[k]) | set(ya[k])):
                if field == "extras":
                    ea, eb = xa[k].get("extras") or {}, ya[k].get("extras") or {}
                    for extra in sorted(set(ea) | set(eb)):
                        if not same(ea.get(extra), eb.get(extra)):
                            got[f"C3.FIELD {table}.extras.{extra}"] += 1
                elif not same(xa[k].get(field), ya[k].get(field)):
                    got[f"C3.FIELD {table}.{field}"] += 1
    drops = Counter()
    for doc, sign in ((reread, 1), (direct, -1)):
        for d in doc.get("diagnostics", []):
            if d["code"].endswith(".RECORD_DROPPED"):
                drops[(d.get("details") or {}).get("class", "")] += sign
    for cls, n in drops.items():
        if n:
            got[f"C3.DROPPED {cls}"] = n


def logs(prefix: str, graph: dict, got: Counter[str]) -> None:
    for message in graph["fatal"]:
        got[f"{prefix}.FATAL {ID_LIKE.sub('<id>', message)}"] += 1
    for message, n in graph["logs"].items():
        if not FATAL.search(message):
            got[f"{prefix}.LOG {message}"] += n


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def render_report(rows: list[tuple[str, str, Counter[str]]]) -> str:
    def total(counts: Counter[str], *prefixes: str) -> int:
        return sum(n for k, n in counts.items() if k.startswith(prefixes))

    out = [
        "## Leg C: CIM-Graph structural comparison",
        "",
        "C1: the source read by both (mRIDs missing from or extra to PowerIO, per "
        "table, and terminal edges that differ). C2: PowerIO's output read by "
        "CIM-Graph (count differences and mRIDs PowerIO read that did not come back). "
        "C3: CIM-Graph's re-serialisation read by PowerIO (records and fields that "
        "differ from PowerIO's direct read, and extra drops). *CIM-Graph warnings* "
        "counts the profile's own messages on reading the document.",
        "",
        "| Case | Profile | Status | C1 ids | C1 edges | C2 counts | C2 ids | C3 records "
        "| C3 fields | C3 drops | CIM-Graph warnings |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for case, status, counts in rows:
        name, _, profile = case.rpartition(" [")
        if not counts and status.startswith("skip"):
            out.append(f"| `{name}` | | {status} | | | | | | | | |")
            continue
        fatal = total(counts, "C1.FATAL", "C2.FATAL", "C3.FATAL")
        state = status if not fatal else f"{status}; CIM-Graph did not load it"
        out.append(
            f"| `{name}` | `{profile.rstrip(']')}` | {state} "
            f"| {total(counts, 'C1.MISSING', 'C1.EXTRA')} "
            f"| {total(counts, 'C1.EDGE')} | {total(counts, 'C2.COUNT')} "
            f"| {total(counts, 'C2.MRID')} | {total(counts, 'C3.MISSING', 'C3.EXTRA', 'C3.UNPARSED')} "
            f"| {total(counts, 'C3.FIELD')} | {total(counts, 'C3.DROPPED')} "
            f"| {total(counts, 'C1.LOG', 'C2.LOG')} |"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        write = Path(sys.argv[4]) if len(sys.argv) > 4 else None
        return worker(Path(sys.argv[2]), Path(sys.argv[3]), write)

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--powerio", default="target/release/powerio")
    parser.add_argument("--corpus", type=Path, default=common.DEFAULT_CORPUS)
    parser.add_argument("--update-expected", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verbose", action="store_true", help="print every count")
    parser.add_argument("--only", help="run only the cases whose name contains this")
    args = parser.parse_args()
    powerio = common.resolve_powerio(args.powerio)
    expected = common.Expected(EXPECTED)

    rows: list[tuple[str, str, Counter[str]]] = []
    failures = 0

    def record(case: str, got: Counter[str]) -> None:
        nonlocal failures
        diff = expected.check(case, got)
        status = "ok" if not diff or args.update_expected else "FAIL"
        if diff and not args.update_expected:
            failures += 1
            print(f"FAIL {case}")
            print("\n".join(diff))
        elif args.verbose:
            print(f"{status} {case}")
            for key, n in sorted(got.items()):
                print(f"  {n:6d}  {key}")
        rows.append((case, status, got))
        common.append_result(case, "cim_cimgraph", status)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        sources = dict(common.cim_sources(args.corpus))
        # Every fixture's output (C2), and every CIM source (C1, C3) with its
        # output (C2).
        cases: list[tuple[str, Path]] = [
            (p.as_posix(), p) for p in common.fixtures() if p.parent.name != "cim"
        ]
        cases += [(case, path) for case, path in sources.items() if path is not None]
        for case, path in sources.items():
            if path is None:
                rows.append((f"{case} [-]", "skip (not fetched)", Counter()))
                common.append_result(case, "cim_cimgraph", "skip")
        for index, (case, path) in enumerate(cases):
            if args.only and args.only not in case:
                continue
            sub = work / str(index)
            sub.mkdir()
            doc = common.serialize(powerio, path, sub / f"{path.name}.pio.json")
            if doc is None:
                continue
            is_cim = case in sources
            out = sub / f"{path.name}.cim.xml"
            log: list[str] = []
            refusal = common.convert(powerio, sub / f"{path.name}.pio.json", "cim-dist", out, log)
            for profile in PROFILES:
                if is_cim:
                    got: Counter[str] = Counter()
                    # Under the source's own name: PowerIO names the network
                    # after the file.
                    (sub / profile).mkdir()
                    rewritten = sub / profile / path.name
                    graph = run_worker(profile, path, sub, rewritten)
                    logs("C1", graph, got)
                    if not graph["fatal"]:
                        c1(graph, doc, got)
                        reread = common.serialize(
                            powerio, rewritten, sub / f"{profile}.reread.pio.json"
                        )
                        c3(doc, reread, got)
                    record(f"{case} source [{profile}]", got)
                got = Counter()
                if refusal:
                    got[f"C2.NOT_WRITTEN {refusal}"] = 1
                else:
                    graph = run_worker(profile, out, sub)
                    logs("C2", graph, got)
                    if not graph["fatal"]:
                        c2(graph, doc, doc if is_cim else None, log, got)
                record(f"{case} output [{profile}]", got)

    if args.update_expected:
        expected.write()
    if args.report:
        common.write_text(args.report, render_report(rows))
    checked = sum(1 for _, status, _ in rows if not status.startswith("skip"))
    print(f"{checked} comparisons, {failures} differ from {EXPECTED.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
