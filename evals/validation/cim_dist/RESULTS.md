# Distribution CIM validation results

Rendered by `run_cim_dist_validation.sh` from the last run of each leg; see README.md for what each one checks.

## Leg B: census

What PowerIO reads from each CIM source. Tables are reconciled with the source classes they map from, less reported drops; *unexplained* counts records that reconciliation does not account for. *Line codes* are those taken from a `PerLengthImpedance`, plus those derived per segment or phase subset. *Unmapped* counts objects of classes the reader has no table for (`CLASS_UNMAPPED`).

| Case | Status | Objects | Buses | Lines | Line codes | Transformers | Loads | Switches | Shunts | Sources | Dropped | Unmapped | Unexplained | To .dss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tests/data/dist/cim/micro_feeder.xml` | ok | 40 | 4 | 1 | 1 + 0 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | yes |
| `corpus/IEEE13.xml` | ok | 509 | 22 | 11 | 7 + 0 | 6 | 16 | 5 | 2 | 1 | 0 | 233 | 0 | yes |
| `corpus/IEEE13_Assets.xml` | ok | 429 | 16 | 11 | 1 + 10 | 5 | 15 | 1 | 2 | 1 | 0 | 226 | 0 | no: `BUILD.DIST.ELECTRICAL_INCOMPLETE` |
| `corpus/IEEE37.xml` | ok | 816 | 39 | 36 | 30 + 0 | 4 | 30 | 0 | 0 | 1 | 0 | 269 | 0 | yes |
| `corpus/IEEE123.xml` | ok | 2077 | 130 | 118 | 29 + 0 | 8 | 91 | 8 | 4 | 1 | 0 | 788 | 0 | yes |
| `corpus/IEEE8500.xml` | ok | 59918 | 4876 | 3661 | 80 + 4 | 1190 | 1177 | 38 | 10 | 1 | 0 | 23239 | 0 | yes |
| `corpus/final9500nodebalanced.xml` | ok | 69269 | 5294 | 3909 | 11 + 2627 | 1304 | 1275 | 107 | 10 | 1 | 0 | 26760 | 0 | no: `BUILD.DIST.ELECTRICAL_INCOMPLETE` |

## Leg C: CIM-Graph structural comparison

C1: the source read by both (mRIDs missing from or extra to PowerIO, per table, and terminal edges that differ). C2: PowerIO's output read by CIM-Graph (count differences and mRIDs PowerIO read that did not come back). C3: CIM-Graph's re-serialisation read by PowerIO (records and fields that differ from PowerIO's direct read, and extra drops). *CIM-Graph warnings* counts the profile's own messages on reading the document.

| Case | Profile | Status | C1 ids | C1 edges | C2 counts | C2 ids | C3 records | C3 fields | C3 drops | CIM-Graph warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| `tests/data/dist/micro/defaults_degenerate.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/defaults_degenerate.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/fourwire_linecode.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/fourwire_linecode.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/ibr_pv_control.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/ibr_pv_control.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/lindist3flow_oracle.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/lindist3flow_oracle.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/linecode_10x10.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/linecode_10x10.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/neutral_grounding_reactor.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/neutral_grounding_reactor.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/onephase_cvr_load.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/onephase_cvr_load.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/onephase_zip_load.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/onephase_zip_load.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/switch.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/micro/switch.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_1ph_delta_wye.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_1ph_delta_wye.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_center_tap.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_center_tap.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_delta_wye.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_delta_wye.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_open_wye_open_delta.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_open_wye_open_delta.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_single_phase.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_single_phase.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/micro/xfmr_wye_delta.dss output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/micro/xfmr_wye_delta.dss output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/pmd/fourwire_linecode.json output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `tests/data/dist/pmd/fourwire_linecode.json output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/pmd/ieee13.json output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/pmd/ieee13.json output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/bmopf/example_enwl_n1_f2.json output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/bmopf/example_enwl_n1_f2.json output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/bmopf/example_ieee13.json output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `tests/data/dist/bmopf/example_ieee13.json output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `tests/data/dist/cim/micro_feeder.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 14 | 0 | 44 |
| `tests/data/dist/cim/micro_feeder.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 15 |
| `tests/data/dist/cim/micro_feeder.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 13 | 0 | 42 |
| `tests/data/dist/cim/micro_feeder.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 13 |
| `corpus/IEEE13.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 4 | 8 | 6 | 12 |
| `corpus/IEEE13.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 |
| `corpus/IEEE13.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 30 |
| `corpus/IEEE13.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/IEEE13_Assets.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 5 | 2 | 5 | 15 |
| `corpus/IEEE13_Assets.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/IEEE13_Assets.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 19 |
| `corpus/IEEE13_Assets.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/IEEE37.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 2 | 4 | 4 | 8 |
| `corpus/IEEE37.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| `corpus/IEEE37.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 41 |
| `corpus/IEEE37.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/IEEE123.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 6 | 14 | 8 | 17 |
| `corpus/IEEE123.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |
| `corpus/IEEE123.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 132 |
| `corpus/IEEE123.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/IEEE8500.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 1189 | 4648 | 1190 | 1205 |
| `corpus/IEEE8500.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1192 |
| `corpus/IEEE8500.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 4879 |
| `corpus/IEEE8500.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/final9500nodebalanced.xml source` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 1293 | 2676 | 1304 | 1318 |
| `corpus/final9500nodebalanced.xml output` | `rc4_2021` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `corpus/final9500nodebalanced.xml source` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 22 | 11 | 5831 |
| `corpus/final9500nodebalanced.xml output` | `cim17v40` | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Leg D: schema conformance

Vocabulary errors against `cim17v40` and profile warnings against `rc4_2021` (CIM-Graph profile classes), per case.

| Case | Status | Vocabulary errors | Profile warnings |
|---|---|---|---|
| `tests/data/dist/micro/defaults_degenerate.dss output` | ok | 0 | 9 |
| `tests/data/dist/micro/fourwire_linecode.dss output` | ok | 0 | 6 |
| `tests/data/dist/micro/ibr_pv_control.dss output` | ok | 0 | 6 |
| `tests/data/dist/micro/lindist3flow_oracle.dss output` | ok | 0 | 4 |
| `tests/data/dist/micro/linecode_10x10.dss output` | ok | 0 | 4 |
| `tests/data/dist/micro/neutral_grounding_reactor.dss output` | ok | 0 | 7 |
| `tests/data/dist/micro/onephase_cvr_load.dss output` | ok | 0 | 4 |
| `tests/data/dist/micro/onephase_zip_load.dss output` | ok | 0 | 4 |
| `tests/data/dist/micro/switch.dss output` | ok | 0 | 8 |
| `tests/data/dist/micro/xfmr_1ph_delta_wye.dss output` | ok | 0 | 6 |
| `tests/data/dist/micro/xfmr_center_tap.dss output` | ok | 0 | 10 |
| `tests/data/dist/micro/xfmr_delta_wye.dss output` | ok | 0 | 6 |
| `tests/data/dist/micro/xfmr_open_wye_open_delta.dss output` | ok | 0 | 10 |
| `tests/data/dist/micro/xfmr_single_phase.dss output` | ok | 0 | 6 |
| `tests/data/dist/micro/xfmr_wye_delta.dss output` | ok | 0 | 6 |
| `tests/data/dist/pmd/fourwire_linecode.json output` | ok | 0 | 6 |
| `tests/data/dist/pmd/ieee13.json output` | ok | 0 | 54 |
| `tests/data/dist/bmopf/example_enwl_n1_f2.json output` | ok; not written: `PARSE.CLI.ERRORS_REPORTED` | | |
| `tests/data/dist/bmopf/example_ieee13.json output` | ok | 0 | 22 |
| `tests/data/dist/cim/micro_feeder.xml source` | ok | 6 | 13 |
| `tests/data/dist/cim/micro_feeder.xml output` | ok | 0 | 11 |
| `corpus/IEEE13.xml source` | ok | 31 | 26 |
| `corpus/IEEE13.xml output` | ok | 0 | 65 |
| `corpus/IEEE13_Assets.xml source` | ok | 21 | 37 |
| `corpus/IEEE13_Assets.xml output` | ok; not written: `BUILD.DIST.ELECTRICAL_INCOMPLETE` | | |
| `corpus/IEEE37.xml source` | ok | 41 | 20 |
| `corpus/IEEE37.xml output` | ok | 0 | 113 |
| `corpus/IEEE123.xml source` | ok | 137 | 34 |
| `corpus/IEEE123.xml output` | ok | 0 | 362 |
| `corpus/IEEE8500.xml source` | ok | 4897 | 1227 |
| `corpus/IEEE8500.xml output` | ok | 0 | 9779 |
| `corpus/final9500nodebalanced.xml source` | ok | 5715 | 1452 |
| `corpus/final9500nodebalanced.xml output` | ok; not written: `BUILD.DIST.ELECTRICAL_INCOMPLETE` | | |
