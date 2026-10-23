#!/usr/bin/env python3
"""Leg B of the distribution CIM validation: the census.

What PowerIO reads from each CIM source, with no oracle beyond the source
itself. Per case:

- the class counts of the source, streamed independently of PowerIO;
- PowerIO's `MulticonductorNetwork` table counts, each reconciled with the
  source classes it maps from: a table holds every object of its classes
  less the ones PowerIO reports dropping (`RECORD_DROPPED`), and any
  difference left over is recorded as `MAP.UNEXPLAINED`;
- the diagnostic code histogram, keyed by code, CIM class and property, so
  `IMPEDANCE_UNRESOLVED` and `RECORD_DROPPED` break out by class;
- whether conversion to `.dss` succeeds, and the refusal code if not.

Every case's counts are compared with `census_expected.json`; a count that
changes fails the run. `--update-expected` rewrites that file from the
current run; review its diff before committing it.

    python evals/validation/cim_dist/census.py --powerio target/release/powerio \
        [--corpus tests/data/large/cim_dist] [--report census.md]

Run it from the repository root; `run_cim_dist_validation.sh` runs every leg.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

EXPECTED = common.HERE / "census_expected.json"

# The switch classes the reader maps (`SWITCH_CLASSES` in
# powerio-dist/src/cim/read.rs).
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

# Each table and the source classes its records come from. Transformers are
# reconciled separately: a tank is one transformer, and a PowerTransformer
# is one only when no tank belongs to it. Line codes are not reconciled: the
# reader makes them as segments use them, one per PerLengthImpedance (with
# its `cim_mrid`), plus one per other phase subset of a phase matrix and one
# per segment that states its own series impedance or none it can use.
TABLE_CLASSES = {
    "buses": ["ConnectivityNode"],
    "lines": ["ACLineSegment"],
    "loads": ["EnergyConsumer"],
    "shunts": ["LinearShuntCompensator"],
    "sources": ["EnergySource"],
    "switches": SWITCH_CLASSES,
    "generators": [],
}
TABLES = [*TABLE_CLASSES, "transformers"]


def source_census(path: Path) -> tuple[Counter[str], int]:
    """Class counts of the source, and how many PowerTransformers own no
    tank (each of which is one transformer of its own)."""
    classes: Counter[str] = Counter()
    power_transformers: set[str] = set()
    with_tanks: set[str] = set()
    for obj in common.read_objects(path):
        classes[obj.cls] += 1
        if obj.cls == "PowerTransformer":
            power_transformers.add(common.mrid(obj.id))
        elif obj.cls == "TransformerTank":
            for _, name, _, resource, _ in obj.props:
                if name == "TransformerTank.PowerTransformer" and resource:
                    with_tanks.add(common.mrid(resource))
    return classes, len(power_transformers - with_tanks)


def code_key(diag: dict) -> tuple[str, int]:
    """A diagnostic as `code class property` and the objects it counts."""
    details = diag.get("details") or {}
    parts = [diag["code"], details.get("class", ""), details.get("property", "")]
    return " ".join(p for p in parts if p), int(details.get("count", 1))


def dropped_by_class(diagnostics: list[dict]) -> Counter[str]:
    dropped: Counter[str] = Counter()
    for diag in diagnostics:
        if diag["code"].endswith(".RECORD_DROPPED"):
            details = diag.get("details") or {}
            dropped[details.get("class", "")] += int(details.get("count", 1))
    return dropped


def census_case(powerio: str, path: Path, work: Path) -> tuple[Counter[str], dict]:
    """The counts compared with the expected file, and the row the report
    renders."""
    got: Counter[str] = Counter()
    classes, pt_alone = source_census(path)
    doc = common.serialize(powerio, path, work / f"{path.name}.pio.json")
    if doc is None:
        got["PARSE.FAILED"] = 1
        return got, {"parsed": False}
    tables = common.network(doc)
    diagnostics = doc.get("diagnostics", [])
    for diag in diagnostics:
        key, n = code_key(diag)
        got[f"CODE {key}"] += n
    dropped = dropped_by_class(diagnostics)

    expected_rows: dict[str, int] = {}
    for table, cims in TABLE_CLASSES.items():
        expected_rows[table] = sum(classes[c] - dropped[c] for c in cims)
    expected_rows["transformers"] = (
        classes["TransformerTank"]
        - dropped["TransformerTank"]
        + pt_alone
        - dropped["PowerTransformer"]
    )
    carried = {t: len(tables.get(t) or []) for t in TABLES}
    for table in TABLES:
        got[f"TABLE {table}"] = carried[table]
        gap = carried[table] - expected_rows[table]
        if gap:
            got[f"MAP.UNEXPLAINED {table}"] = gap
    codes = tables.get("linecodes") or []
    from_pli = sum(1 for c in codes if "cim_mrid" in (c.get("extras") or {}))
    got["LINECODES from PerLengthImpedance"] = from_pli
    got["LINECODES derived"] = len(codes) - from_pli

    refusal = common.convert(powerio, path, "dss", work / f"{path.stem}.dss")
    if refusal:
        got[f"DSS.REFUSED {refusal}"] = 1
    row = {
        "parsed": True,
        "objects": sum(classes.values()),
        "carried": carried,
        "linecodes": (from_pli, len(codes) - from_pli),
        "dropped": sum(dropped.values()),
        "unmapped": sum(
            n for k, n in got.items() if k.startswith("CODE ") and ".CLASS_UNMAPPED" in k
        ),
        "unexplained": sum(abs(n) for k, n in got.items() if k.startswith("MAP.UNEXPLAINED")),
        "dss": refusal or "yes",
    }
    return got, row


def render_report(rows: list[tuple[str, str, dict]]) -> str:
    out = [
        "## Leg B: census",
        "",
        "What PowerIO reads from each CIM source. Tables are reconciled with the "
        "source classes they map from, less reported drops; *unexplained* counts "
        "records that reconciliation does not account for. *Line codes* are those "
        "taken from a `PerLengthImpedance`, plus those derived per segment or "
        "phase subset. *Unmapped* counts objects of classes the reader has no "
        "table for (`CLASS_UNMAPPED`).",
        "",
        "| Case | Status | Objects | Buses | Lines | Line codes | Transformers | Loads "
        "| Switches | Shunts | Sources | Dropped | Unmapped | Unexplained | To .dss |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for case, status, row in rows:
        if not row.get("parsed"):
            out.append(f"| `{case}` | {status} | | | | | | | | | | | | | |")
            continue
        c = row["carried"]
        from_pli, derived = row["linecodes"]
        dss = "yes" if row["dss"] == "yes" else f"no: `{row['dss']}`"
        out.append(
            f"| `{case}` | {status} | {row['objects']} | {c['buses']} | {c['lines']} "
            f"| {from_pli} + {derived} | {c['transformers']} | {c['loads']} "
            f"| {c['switches']} | {c['shunts']} | {c['sources']} | {row['dropped']} "
            f"| {row['unmapped']} | {row['unexplained']} | {dss} |"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--powerio", default="target/release/powerio")
    parser.add_argument("--corpus", type=Path, default=common.DEFAULT_CORPUS)
    parser.add_argument("--update-expected", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verbose", action="store_true", help="print every count")
    args = parser.parse_args()
    powerio = common.resolve_powerio(args.powerio)
    expected = common.Expected(EXPECTED)

    rows: list[tuple[str, str, dict]] = []
    failures = checked = 0
    with tempfile.TemporaryDirectory() as tmp:
        for case, path in common.cim_sources(args.corpus):
            if path is None:
                rows.append((case, "skip (not fetched)", {}))
                common.append_result(case, "cim_census", "skip")
                continue
            checked += 1
            got, row = census_case(powerio, path, Path(tmp))
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
            rows.append((case, status, row))
            common.append_result(case, "cim_census", status)

    if args.update_expected:
        expected.write()
    if args.report:
        common.write_text(args.report, render_report(rows))
    print(f"{checked} sources counted, {failures} cases differ from {EXPECTED.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
