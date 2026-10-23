#!/usr/bin/env bash
# Leg D of the distribution CIM validation alone: schema conformance of
# PowerIO's cim-dist output and of the CIM sources, against the CIM-Graph
# profile classes. See README.md in this directory.
#
#   bash evals/validation/cim_dist/run_schema_check.sh [schema_check.py args]
#
# The environment is run_cim_dist_validation.sh's (POWERIO, CIM_VENV,
# CIM_DIST_CORPUS, CIM_DIST_FETCH). Updates the leg D section of
# evals/validation/cim_dist/RESULTS.md and exits nonzero when any case
# differs from schema_expected.json.

set -euo pipefail
exec bash "$(dirname "$0")/run_cim_dist_validation.sh" schema -- "$@"
