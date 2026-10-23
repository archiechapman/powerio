#!/usr/bin/env python3
"""Leg D of the distribution CIM validation: schema conformance.

Checks CIM RDF/XML documents against the profile classes CIM-Graph
generates from the CIM UML, in two passes:

- vocabulary, against `cim17v40` (errors): every class exists; every
  property is declared on the object's class or an ancestor; attributes are
  literals and associations are references; enumeration values are members
  of the declared enumeration; integer, float and boolean literals parse; a
  reference to an object in the document names an object of the declared
  target class.
- profile, against `rc4_2021`, the GridAPPS-D CIM100 profile (warnings): the
  classes and properties the document uses that the profile leaves out. A
  valid CIM document can use classes a given profile omits, so these are
  recorded, not refused.

It runs on PowerIO's fresh `cim-dist` output for every distribution fixture
and for every corpus feeder present, and on the CIM sources themselves as a
control. Every case's findings are compared with `schema_expected.json`, so
an upstream quirk is recorded once and a new finding, or a finding that
disappears, fails the run. `--update-expected` rewrites that file from the
current run; review its diff before committing it.

Fresh output comes from the PowerIO CLI as `serialize` then `convert` from
the PowerIO IR document, which carries no retained source bytes, so a CIM
source is written canonically instead of echoed.

    python evals/validation/cim_dist/schema_check.py \
        --powerio target/release/powerio \
        [--corpus tests/data/large/cim_dist] [--report RESULTS.md]

Run it from the repository root in the `.venv-cim` environment
(`requirements-cim.txt`); `run_schema_check.sh` does both.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import importlib
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import Obj, fixtures, fresh_cim, read_objects

VOCABULARY_PROFILE = "cim17v40"
PROFILE = "rc4_2021"

# Finding codes. Vocabulary findings are errors, profile findings warnings.
CLASS_UNKNOWN = "VOCAB.CLASS_UNKNOWN"
PROPERTY_UNKNOWN = "VOCAB.PROPERTY_UNKNOWN"
PROPERTY_WRONG_CLASS = "VOCAB.PROPERTY_WRONG_CLASS"
NAMESPACE_UNKNOWN = "VOCAB.NAMESPACE_UNKNOWN"
EXPECTED_REFERENCE = "VOCAB.EXPECTED_REFERENCE"
EXPECTED_LITERAL = "VOCAB.EXPECTED_LITERAL"
ENUM_VALUE = "VOCAB.ENUM_VALUE"
LITERAL_INVALID = "VOCAB.LITERAL_INVALID"
REFERENCE_TYPE = "VOCAB.REFERENCE_TYPE"
PROFILE_CLASS = "PROFILE.CLASS_OUTSIDE"
PROFILE_PROPERTY = "PROFILE.PROPERTY_OUTSIDE"

EXPECTED = common.HERE / "schema_expected.json"
EXAMPLES = common.EXAMPLES


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Prop:
    """One property as the profile declares it."""

    association: bool
    # The declared value type: a profile class (association target or
    # enumeration) or a primitive name (`int`, `float`, `bool`, `str`).
    target: type | str | None
    namespace: str


class Profile:
    """The classes, properties and enumerations of one CIM-Graph profile."""

    def __init__(self, name: str) -> None:
        module = importlib.import_module(f"cimgraph.data_profile.{name}.{name}")
        self.name = name
        self.namespace = module.ONTOLOGY_URI
        self.classes: dict[str, type] = {}
        self.enums: dict[str, type[enum.Enum]] = {}
        for attr, value in vars(module).items():
            if not isinstance(value, type):
                continue
            if issubclass(value, enum.Enum):
                self.enums[attr] = value
            elif dataclasses.is_dataclass(value):
                self.classes[attr] = value
        self._props: dict[tuple[str, str], Prop | None] = {}

    def prop(self, cls: str, name: str) -> Prop | None:
        """Property `name` declared on class `cls` itself, not inherited."""
        key = (cls, name)
        if key not in self._props:
            self._props[key] = self._declared(cls, name)
        return self._props[key]

    def _declared(self, cls: str, name: str) -> Prop | None:
        klass = self.classes.get(cls)
        if klass is None or name not in vars(klass).get("__annotations__", {}):
            return None
        field = next(f for f in dataclasses.fields(klass) if f.name == name)
        meta = field.metadata
        return Prop(
            association=meta.get("type") == "Association",
            target=self._resolve(field.type),
            namespace=meta.get("namespace", self.namespace),
        )

    def _resolve(self, annotation) -> type | str | None:
        """`Optional[float | ResistancePerLength]` to `float`,
        `list[Terminal]` to the `Terminal` class."""
        text = annotation if isinstance(annotation, str) else str(annotation)
        text = re.sub(r"^(Optional|list|List)\[(.*)\]$", r"\2", text.strip())
        text = re.sub(r"^(Optional|list|List)\[(.*)\]$", r"\2", text.strip())
        first = text.split("|")[0].strip()
        if first in ("int", "float", "bool", "str"):
            return first
        return self.classes.get(first) or self.enums.get(first)

    def is_a(self, cls: str, ancestor: str) -> bool:
        klass, base = self.classes.get(cls), self.classes.get(ancestor)
        return klass is not None and base is not None and issubclass(klass, base)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


class Findings:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = {}

    def add(self, code: str, subject: str, example: str) -> None:
        key = f"{code} {subject}"
        self.counts[key] += 1
        examples = self.examples.setdefault(key, [])
        if len(examples) < EXAMPLES and example not in examples:
            examples.append(example)


def literal_ok(kind: str, text: str) -> bool:
    try:
        if kind == "int":
            int(text)
        elif kind == "float":
            float(text)
        elif kind == "bool":
            return text in ("true", "false", "1", "0")
    except ValueError:
        return False
    return True


def check_vocabulary(objects: list[Obj], vocab: Profile, out: Findings) -> None:
    class_of = {o.id: o.cls for o in objects if o.ns == vocab.namespace}
    for o in objects:
        if o.ns != vocab.namespace:
            out.add(NAMESPACE_UNKNOWN, f"{{{o.ns}}}{o.cls}", o.id)
            continue
        if o.cls not in vocab.classes:
            out.add(CLASS_UNKNOWN, o.cls, o.id)
            continue
        for pns, name, text, resource, nested in o.props:
            owner, _, prop = name.rpartition(".")
            if pns != vocab.namespace:
                out.add(NAMESPACE_UNKNOWN, f"{{{pns}}}{name}", o.id)
                continue
            if not vocab.is_a(o.cls, owner):
                out.add(PROPERTY_WRONG_CLASS, f"{o.cls} {name}", o.id)
                continue
            declared = vocab.prop(owner, prop)
            if declared is None:
                out.add(PROPERTY_UNKNOWN, name, o.id)
                continue
            if nested:
                continue
            target = declared.target
            if declared.association:
                if resource is None:
                    out.add(EXPECTED_REFERENCE, name, o.id)
                elif isinstance(target, type) and resource.lstrip("#") in class_of:
                    named = class_of[resource.lstrip("#")]
                    if not vocab.is_a(named, target.__name__):
                        out.add(REFERENCE_TYPE, f"{name} -> {named}", o.id)
                continue
            if isinstance(target, type) and issubclass(target, enum.Enum):
                value = (resource or "").rpartition("#")[2]
                enum_name, _, member = value.partition(".")
                if resource is None or not resource.startswith(vocab.namespace):
                    out.add(EXPECTED_REFERENCE, name, o.id)
                elif enum_name != target.__name__ or member not in target.__members__:
                    out.add(ENUM_VALUE, f"{name} = {value}", o.id)
                continue
            if resource is not None:
                out.add(EXPECTED_LITERAL, name, o.id)
            elif isinstance(target, str) and not literal_ok(target, text or ""):
                out.add(LITERAL_INVALID, name, f"{o.id}: {text!r}")


def check_profile(objects: list[Obj], profile: Profile, out: Findings) -> None:
    for o in objects:
        if o.ns != profile.namespace:
            continue
        if o.cls not in profile.classes:
            out.add(PROFILE_CLASS, o.cls, o.id)
            continue
        for pns, name, *_ in o.props:
            owner, _, prop = name.rpartition(".")
            if pns == profile.namespace and profile.prop(owner, prop) is None:
                out.add(PROFILE_PROPERTY, name, o.id)


def check_document(path: Path, vocab: Profile, profile: Profile) -> Findings:
    objects = read_objects(path)
    out = Findings()
    check_vocabulary(objects, vocab, out)
    check_profile(objects, profile, out)
    return out


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def append_result(case: str, mark: str) -> None:
    common.append_result(case, "cim_schema", mark)


def render_report(rows: list[tuple[str, str, Counter[str]]]) -> str:
    out = [
        "## Leg D: schema conformance",
        "",
        f"Vocabulary errors against `{VOCABULARY_PROFILE}` and profile warnings "
        f"against `{PROFILE}` (CIM-Graph profile classes), per case.",
        "",
        "| Case | Status | Vocabulary errors | Profile warnings |",
        "|---|---|---|---|",
    ]
    for case, status, counts in rows:
        refused = [k.split(" ", 1)[1] for k in counts if k.startswith("CONVERT.REFUSED")]
        if refused:
            out.append(f"| `{case}` | {status}; not written: `{refused[0]}` | | |")
            continue
        vocab = sum(n for k, n in counts.items() if k.startswith("VOCAB."))
        prof = sum(n for k, n in counts.items() if k.startswith("PROFILE."))
        out.append(f"| `{case}` | {status} | {vocab} | {prof} |")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--powerio", default="target/release/powerio")
    parser.add_argument("--corpus", type=Path, default=common.DEFAULT_CORPUS)
    parser.add_argument("--update-expected", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verbose", action="store_true", help="print every finding")
    args = parser.parse_args()
    args.powerio = common.resolve_powerio(args.powerio)

    vocab = Profile(VOCABULARY_PROFILE)
    profile = Profile(PROFILE)
    expected = common.Expected(EXPECTED)

    # (case id, document or None, reason when None)
    cases: list[tuple[str, Path | None, str]] = []
    failures = 0
    rows: list[tuple[str, str, Counter[str]]] = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for path in fixtures():
            if path.suffix == ".xml":
                cases.append((f"{path.as_posix()} source", path, ""))
            sub = work / path.parent.name
            sub.mkdir(exist_ok=True)
            out, why = fresh_cim(args.powerio, path, sub)
            if why == "unparsed":
                continue
            cases.append((f"{path.as_posix()} output", out, why))
        for feeder in common.corpus_feeders():
            path = args.corpus / feeder.file
            case = f"corpus/{feeder.file}"
            if not path.exists():
                rows.append((f"{case} source", "skip (not fetched)", Counter()))
                append_result(case, "skip")
                continue
            cases.append((f"{case} source", path, ""))
            sub = work / "corpus"
            sub.mkdir(exist_ok=True)
            out, why = fresh_cim(args.powerio, path, sub)
            cases.append((f"{case} output", out, why))

        for case, doc, why in cases:
            got: Counter[str] = Counter()
            examples: dict[str, list[str]] = {}
            if doc is None:
                got[f"CONVERT.REFUSED {why}"] = 1
                examples[f"CONVERT.REFUSED {why}"] = [args.powerio]
            else:
                findings = check_document(doc, vocab, profile)
                got, examples = findings.counts, findings.examples
            diff = expected.check(case, got)
            status = "ok" if not diff else "FAIL"
            if diff and not args.update_expected:
                failures += 1
                print(f"FAIL {case}")
                print("\n".join(diff))
                for key in sorted(examples):
                    print(f"    e.g. {key}: {', '.join(examples[key])}")
            elif args.verbose:
                print(f"{status} {case}")
                for key, n in sorted(got.items()):
                    print(f"  {n:6d}  {key}  e.g. {', '.join(examples[key])}")
            rows.append((case, "ok" if not diff or args.update_expected else "FAIL", got))
            append_result(case, rows[-1][1])

    if args.update_expected:
        expected.write()
    if args.report:
        common.write_text(args.report, render_report(rows))
    checked = sum(1 for _, doc, _ in cases if doc is not None)
    print(f"{checked} documents checked, {failures} cases differ from {EXPECTED.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
