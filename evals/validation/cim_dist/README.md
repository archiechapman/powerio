# Distribution CIM validation

Opt-in validation of the `cim-dist` reader and writer against independent CIM
tooling, run on PowerIO's own fixtures and on public distribution feeders.
Nothing here runs in `cargo test` or the default CI gate.

```
bash evals/validation/cim_dist/run_cim_dist_validation.sh            # every leg
bash evals/validation/cim_dist/run_cim_dist_validation.sh census     # one or more legs
bash evals/validation/cim_dist/run_cim_dist_validation.sh -- --update-expected
```

The runner creates the `.venv-cim` virtualenv (`requirements-cim.txt`;
`CIM_VENV` overrides it), fetches the corpus (leg A; `CIM_DIST_FETCH=0`
skips it), builds the CLI if `POWERIO` is unset and none is built, runs the
legs, and replaces their sections of `RESULTS.md`. It exits nonzero when any
case differs from its leg's `*_expected.json`. Each leg is also a script that
runs on its own (`--help`). A full run takes a few minutes (four on a
laptop), most of it CIM-Graph on the two large feeders.

| Leg | Script | Checks |
|---|---|---|
| A | `fetch_corpus.sh`, `manifest.toml` | The corpus, pinned by commit and SHA-256 |
| B | `census.py` | What PowerIO reads from each CIM source, reconciled with the source |
| C | `cimgraph_compare.py` | Structure against CIM-Graph, in three directions |
| D | `schema_check.py` | PowerIO's output and the sources against CIM-Graph's profile classes |

The OpenDSS electrical comparison and benchmark legs join them in later
changes (#456). The expected files were recorded with the reader and writer
of `main` plus #680 (transformer tanks).

## Leg A: corpus

```
bash evals/validation/cim_dist/fetch_corpus.sh
```

`manifest.toml` names each feeder with its source commit, size and SHA-256.
The fetch script downloads only those files into `tests/data/large/cim_dist/`
(gitignored, or `CIM_DIST_CORPUS`), keeps a file already present with the
right digest, and fails on a mismatch. The feeders are GridAPPS-D
Powergrid-Models `releases/2024.06.0` `platform/cimxml` at commit `2ec0ba4`
(IEEE 13, IEEE 13 Assets, IEEE 37, IEEE 123, IEEE 8500, and the 9500 node
balanced feeder). They are fetched, never vendored: the release branch has no
licence file at its root. Every leg skips a feeder that is absent, so the
fixture cases run with no download.

## Leg B: census

`census.py` takes each CIM source (`tests/data/dist/cim/*.xml` and the
corpus) and records, with no oracle beyond the source itself:

- the source's class counts, streamed independently of PowerIO;
- PowerIO's table counts, each reconciled with the source classes it maps
  from: buses from `ConnectivityNode`, lines from `ACLineSegment`, loads from
  `EnergyConsumer`, shunts from `LinearShuntCompensator`, sources from
  `EnergySource`, switches from the switch classes, and transformers from
  each `TransformerTank` and each `PowerTransformer` that owns no tank. A
  table holds every object of its classes less the ones PowerIO reports
  dropping (`RECORD_DROPPED`); anything left over is `MAP.UNEXPLAINED`.
  Line codes are not reconciled, because the reader makes them as segments
  use them; they are split into those taken from a `PerLengthImpedance` and
  those derived per segment or phase subset;
- PowerIO's diagnostics, counted by code, CIM class and property;
- whether conversion to `.dss` succeeds, or its refusal code.

| | |
|---|---|
| Oracle | The source document itself (class counts and references) |
| Settings | PowerIO CLI from the working tree (`POWERIO`): `serialize` for the tables and diagnostics, `convert --to dss` for the conversion |
| Identity mapping | Tables to source classes as above; drops by the `class` of each `RECORD_DROPPED` diagnostic |
| Tolerances | Exact: every count equals the expected count |
| Expected codes | `census_expected.json`, per case |

What it found first: every table reconciles on all seven sources, with
nothing unexplained. IEEE 8500 reads 1,190 transformers and the 9500 node
feeder 1,304. IEEE 13 Assets and the 9500 node feeder do not convert to
`.dss` (`BUILD.DIST.ELECTRICAL_INCOMPLETE`): 2,622 of the 9500 node feeder's
3,909 segments are on wire geometry (`IMPEDANCE_UNRESOLVED`).

## Leg C: CIM-Graph structural comparison

`cimgraph_compare.py` compares PowerIO with CIM-Graph in three directions:

- **C1, the source read by both.** Per table, the mRIDs CIM-Graph finds for
  the table's classes equal the `cim_mrid`s PowerIO carries, less PowerIO's
  reported drops; and each piece of equipment PowerIO carries connects to
  the same `ConnectivityNode`s, terminal by terminal (a tank's terminals
  belong to its `PowerTransformer`, as in CIM).
- **C2, PowerIO's fresh output read by CIM-Graph**, for every distribution
  fixture and corpus feeder: it loads; the mRIDs PowerIO read come back
  unchanged; and CIM-Graph's counts per table equal PowerIO's, less the
  records the writer reports dropping.
- **C3, CIM-Graph's re-serialisation of the source read by PowerIO**
  (`cimgraph.utils.write_xml`): the network equals PowerIO's direct read,
  record by record and field by field, and no extra record is dropped. This
  tests PowerIO against a second serializer: `rdf:about` with `urn:uuid:`,
  classes in alphabetical order, and associations stated from whichever end
  CIM-Graph keeps.

Each runs under two profiles, since each loses different data: `rc4_2021`
has no `Asset.PowerSystemResources` or `PowerTransformerEnd.x`, and
`cim17v40` spells `PhotoVoltaicUnit`. CIM-Graph reads its profile from the
environment at import, so it runs in a subprocess per document and profile.
Its parser logs a document it cannot parse as "not found. Skipping." and
carries on with an empty graph; the harness counts that, and an empty graph,
as `FATAL`. Its other warnings (properties outside the profile, identifiers
that are not UUIDs) are counted by message and recorded, since the sources
raise them too.

| | |
|---|---|
| Oracle | CIM-Graph 0.5.0a12 (PNNL, BSD-3): `XMLFile`, `FeederModel`, `write_xml`; profiles `rc4_2021` and `cim17v40`; pinned in `requirements-cim.txt` |
| Settings | PowerIO CLI from the working tree (`POWERIO`); output written from the IR document, so a CIM source is written canonically, not echoed |
| Identity mapping | mRIDs without `#`, `urn:uuid:` or a leading underscore, upper case; CIM-Graph objects by their graph key, which keeps a source identifier that is not a UUID; C3 records by `name` (buses by `id`) |
| Tolerances | Identities and edges exact; C3 numbers within a relative and absolute 1e-9; every count equals the expected count |
| Expected codes | `cimgraph_expected.json`, per case and profile, with notes for every accepted finding |

What it found first:

- C1 and C2 agree on every case: identities, terminal connectivity, mRIDs
  through PowerIO's writer, and counts.
- C3 under `cim17v40` drops every `TransformerCoreAdmittance`, because
  `write_xml` states the association from the end
  (`TransformerEnd.CoreAdmittance`) and PowerIO reads only
  `TransformerCoreAdmittance.TransformerEnd`. That is a reader gap.
- C3 under `rc4_2021` also drops every tank (1,189 on IEEE 8500): the
  profile has no `Asset.PowerSystemResources`, so the link from a catalog
  entry to its tanks is lost before PowerIO sees the document.
- CIM-Graph renames identifiers that are not UUIDs (`micro_feeder.xml`'s
  `_sourcebus`) to UUIDs it derives from them, and drops the reactance of a
  `PowerTransformerEnd` under `rc4_2021`.

## Leg D: schema conformance

```
bash evals/validation/cim_dist/run_schema_check.sh
```

`schema_check.py` reads each CIM RDF/XML document and checks it in two passes
against the profile classes CIM-Graph generates from the CIM UML:

- **Vocabulary, against `cim17v40` (errors).** Every class exists; every
  property is declared on the object's class or an ancestor, under the class
  that qualifies it; attributes are literals and associations are references;
  enumeration values name a member of the declared enumeration; integer,
  float and boolean literals parse; a reference to an object in the document
  names an object of the declared target class.
- **Profile, against `rc4_2021` (warnings).** The classes and properties the
  document uses that the GridAPPS-D CIM100 profile leaves out. A valid CIM
  document can use classes a profile omits, so these are recorded, not
  refused.

It checks:

- PowerIO's fresh `cim-dist` output for every distribution fixture under
  `tests/data/dist/{micro,pmd,bmopf,cim}` that parses as a case, and for every
  corpus feeder present. Fresh output is `powerio serialize` then
  `powerio convert` from the IR document, which carries no retained source
  bytes, so a CIM source is written canonically rather than echoed.
- The CIM sources themselves (`tests/data/dist/cim/*.xml` and the corpus
  feeders), as a control. Their findings are upstream quirks, recorded once.

Every case's findings, counted per code and qualified name, are compared with
`schema_expected.json`; a new finding or one that disappears fails the run.
After a deliberate change, rerun with `--update-expected` and review the diff.
A vocabulary finding on PowerIO output is accepted into that file only with a
note in its `notes` block saying why.

### The five things

| | |
|---|---|
| Oracle | CIM-Graph 0.5.0a12 (PNNL, BSD-3), profiles `cim17v40` (vocabulary) and `rc4_2021` (profile); pinned in `requirements-cim.txt` |
| Settings | PowerIO CLI from the working tree (`POWERIO`); CIM100 namespace `http://iec.ch/TC57/CIM100#` |
| Identity mapping | None needed: each document is checked on its own; findings are keyed by code and CIM qualified name, with up to three example mRIDs |
| Tolerances | Exact: finding counts per key equal the expected counts |
| Expected codes | `schema_expected.json`, per case, with notes for every accepted vocabulary finding |

### What it found first

- PowerIO's writer before #648 used `PhaseImpedanceData.PerLengthPhaseImpedance`,
  which `cim17v40` does not declare (`VOCAB.PROPERTY_UNKNOWN`, one per
  impedance entry). With #648 PowerIO's output has no vocabulary findings.
- `tests/data/dist/cim/micro_feeder.xml` states shunt sections as
  `ShuntCompensatorPhase.bPerSection` and `gPerSection`; `cim17v40` declares
  them on `LinearShuntCompensatorPhase`, which is what the writer emits.
- The Powergrid-Models sources use `PhotovoltaicUnit` (`PhotoVoltaicUnit` in
  `cim17v40`), `BatteryState.Charging` (`BatteryStateKind.charging`),
  `SynchronousMachine.p` (declared on `RotatingMachine`), and
  `RegulatingControl.discrete` and `ConnectivityNode.OperationalLimitSet`,
  which `cim17v40` does not declare.
- PowerIO's tank output (#680) has no vocabulary findings; it uses
  `Asset.PowerSystemResources` as the sources do, which `rc4_2021` omits.

`RESULTS.md` holds the rendered per case tables from the last run of each
leg.
