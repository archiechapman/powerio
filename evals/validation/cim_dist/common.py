"""Helpers the distribution CIM validation legs share: the corpus manifest,
the case list, PowerIO's CLI, streamed RDF/XML reading, and the expected
counts every leg compares against.

The legs import this module by path (`sys.path` holds the script's
directory), so it needs nothing beyond the standard library.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDF_ID = f"{{{RDF}}}ID"
RDF_ABOUT = f"{{{RDF}}}about"
RDF_RESOURCE = f"{{{RDF}}}resource"

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.toml"
FIXTURE_DIRS = ["micro", "pmd", "bmopf", "cim"]
FIXTURE_ROOT = Path("tests/data/dist")
DEFAULT_CORPUS = Path("tests/data/large/cim_dist")
EXAMPLES = 3


# ---------------------------------------------------------------------------
# Manifest and cases
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Feeder:
    """One corpus feeder as `manifest.toml` pins it."""

    file: str
    url: str
    sha256: str
    bytes: int


def manifest() -> dict:
    return tomllib.loads(MANIFEST.read_text(encoding="utf-8"))


def corpus_feeders() -> list[Feeder]:
    doc = manifest()
    feeders = []
    for corpus in doc["corpus"].values():
        base = corpus["base_url"].format(commit=corpus["commit"])
        for entry in corpus["feeders"]:
            feeders.append(
                Feeder(
                    file=entry["file"],
                    url=f"{base}/{entry['file']}",
                    sha256=entry["sha256"],
                    bytes=entry["bytes"],
                )
            )
    return feeders


def fixtures() -> list[Path]:
    """The distribution fixtures, every one a leg may run on."""
    paths = []
    for directory in FIXTURE_DIRS:
        for path in sorted((FIXTURE_ROOT / directory).iterdir()):
            if path.suffix in (".dss", ".json", ".xml"):
                paths.append(path)
    return paths


def cim_sources(corpus: Path) -> list[tuple[str, Path | None]]:
    """The CIM sources: the `cim` fixtures and every manifest feeder, keyed
    by case name. A feeder not fetched comes back with no path."""
    cases: list[tuple[str, Path | None]] = []
    for path in fixtures():
        if path.parent.name == "cim" and path.suffix == ".xml":
            cases.append((path.as_posix(), path))
    for feeder in corpus_feeders():
        path = corpus / feeder.file
        cases.append((f"corpus/{feeder.file}", path if path.exists() else None))
    return cases


# ---------------------------------------------------------------------------
# PowerIO
# ---------------------------------------------------------------------------


def resolve_powerio(path: str) -> str:
    # Windows resolves neither a relative program path nor a missing .exe.
    found = shutil.which(path)
    if found is None:
        sys.exit(f"powerio CLI not found: {path}")
    return os.path.abspath(found)


def refusal_code(stderr: str, returncode: int) -> str:
    codes = re.findall(r"\b([A-Z]+(?:\.[A-Z_]+){2,})\b", stderr)
    return codes[-1] if codes else f"exit {returncode}"


def serialize(powerio: str, source: Path, ir: Path) -> dict | None:
    """PowerIO's IR document for `source`, or None when it does not parse as
    a case. serialize exits nonzero when the reader reports errors (for
    example a segment on wire geometry) but still writes the document."""
    subprocess.run(
        [powerio, "serialize", str(source), "-o", str(ir)],
        check=False,
        capture_output=True,
        text=True,
    )
    if not ir.exists():
        return None
    return json.loads(ir.read_text(encoding="utf-8"))


def convert(
    powerio: str, source: Path, target: str, out: Path, log: list[str] | None = None
) -> str:
    """Convert `source` to `target`; the refusal code, or "" on success. The
    CLI's diagnostic lines are appended to `log` when given."""
    done = subprocess.run(
        [powerio, "convert", str(source), "--to", target, "-o", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    if log is not None:
        log.extend(done.stderr.splitlines())
    return "" if done.returncode == 0 else refusal_code(done.stderr, done.returncode)


def fresh_cim(powerio: str, source: Path, work: Path) -> tuple[Path | None, str]:
    """PowerIO's canonical cim-dist output for `source`, or the reason it
    has none: `unparsed` when the fixture is not a standalone case, or the
    diagnostic code the CLI refused the conversion with.

    Output is written from the IR document, which carries no retained
    source bytes, so a CIM source is written canonically, not echoed."""
    ir = work / f"{source.name}.pio.json"
    out = work / f"{source.name}.cim.xml"
    if serialize(powerio, source, ir) is None:
        return None, "unparsed"
    why = convert(powerio, ir, "cim-dist", out)
    return (None, why) if why else (out, "")


def network(doc: dict) -> dict:
    """The `MulticonductorNetwork` tables of an IR document."""
    return doc["value"]["data"]


def mrid(text: str) -> str:
    """An identifier as both readers spell it: no `#`, `urn:uuid:` or
    leading underscore, upper case."""
    text = text.rpartition("#")[2] if "#" in text else text
    if text.lower().startswith("urn:uuid:"):
        text = text[9:]
    return text.lstrip("_").upper()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Obj:
    ns: str
    cls: str
    id: str
    # (namespace, `Class.property`, literal text or None, reference or None,
    # has nested elements)
    props: list[tuple[str, str, str | None, str | None, bool]]


def split(tag: str) -> tuple[str, str]:
    ns, _, local = tag[1:].partition("}")
    return ns, local


def object_id(elem: ET.Element) -> str:
    if RDF_ID in elem.attrib:
        return elem.attrib[RDF_ID]
    return elem.attrib.get(RDF_ABOUT, "").lstrip("#")


def read_objects(path: Path) -> list[Obj]:
    """The top level objects of an RDF/XML document, streamed so the 40 MB
    feeders do not hold an element tree."""
    objects: list[Obj] = []
    depth = 0
    for event, elem in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            depth += 1
            continue
        depth -= 1
        if depth != 1:
            continue
        ns, cls = split(elem.tag)
        props = []
        for child in elem:
            pns, name = split(child.tag)
            resource = child.attrib.get(RDF_RESOURCE)
            text = None if resource is not None else (child.text or "").strip()
            props.append((pns, name, text, resource, len(child) > 0))
        objects.append(Obj(ns, cls, object_id(elem), props))
        elem.clear()
    return objects


# ---------------------------------------------------------------------------
# Expected counts
# ---------------------------------------------------------------------------


class Expected:
    """A leg's `*_expected.json`: per case, a count per finding key. A case
    passes when its counts equal the recorded ones exactly."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.cases: dict[str, dict[str, int]] = self.doc.get("cases", {})
        self.observed: dict[str, dict[str, int]] = {}

    def check(self, case: str, got: Counter[str]) -> list[str]:
        """Record `got` for `case`; the lines that differ from expected."""
        self.observed[case] = dict(sorted(got.items()))
        expected = self.cases.get(case, {})
        lines = []
        for key in sorted(set(got) | set(expected)):
            if got.get(key, 0) != expected.get(key, 0):
                lines.append(f"  {key}: expected {expected.get(key, 0)}, got {got.get(key, 0)}")
        return lines

    def write(self) -> None:
        # Keep the expectations for corpus cases this run could not see.
        for case, counts in self.cases.items():
            self.observed.setdefault(case, counts)
        self.doc["cases"] = dict(sorted(self.observed.items()))
        write_text(self.path, json.dumps(self.doc, indent=2) + "\n")
        print(f"wrote {self.path}")


def append_result(case: str, leg: str, mark: str) -> None:
    """One `<case>\\t<leg>\\t<mark>` line in `PIO_RESULTS_TSV`, the
    convention the other validators use."""
    out = os.environ.get("PIO_RESULTS_TSV")
    if out:
        with open(out, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{case}\t{leg}\t{mark}\n")


def write_text(path: Path, text: str) -> None:
    """Write with LF line ends on every platform."""
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# RESULTS.md
# ---------------------------------------------------------------------------

RESULTS_TITLE = "# Distribution CIM validation results"
RESULTS_INTRO = (
    "Rendered by `run_cim_dist_validation.sh` from the last run of each leg; "
    "see README.md for what each one checks."
)


def merge_results(results: Path, sections: list[Path]) -> None:
    """Replace the `## Leg X` sections of `results` that `sections` render,
    keeping the others, in leg order."""
    by_leg: dict[str, str] = {}
    if results.exists():
        text = "\n" + results.read_text(encoding="utf-8")
        for part in text.split("\n## Leg ")[1:]:
            by_leg[part[0]] = "## Leg " + part.strip() + "\n"
    for section in sections:
        text = section.read_text(encoding="utf-8").strip() + "\n"
        by_leg[text[len("## Leg ")]] = text
    body = "\n".join(by_leg[leg] for leg in sorted(by_leg))
    write_text(results, f"{RESULTS_TITLE}\n\n{RESULTS_INTRO}\n\n{body}")


if __name__ == "__main__":
    # python common.py merge-results RESULTS.md SECTION.md...
    if len(sys.argv) >= 3 and sys.argv[1] == "merge-results":
        merge_results(Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
    else:
        sys.exit("usage: common.py merge-results RESULTS.md SECTION.md...")
