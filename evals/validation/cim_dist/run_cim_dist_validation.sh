#!/usr/bin/env bash
# The distribution CIM validation: fetch the corpus (leg A), then run the
# census (B), the CIM-Graph structural comparison (C) and schema conformance
# (D). See README.md in this directory.
#
#   bash evals/validation/cim_dist/run_cim_dist_validation.sh [legs] [-- leg args]
#
# legs is any of census, cimgraph, schema (default: all three). Arguments
# after `--` go to every leg, for example `-- --update-expected`.
#
# Environment:
#   POWERIO          the powerio CLI (default target/release/powerio, built if absent)
#   CIM_VENV         the validation virtualenv (default .venv-cim, created if absent)
#   CIM_DIST_CORPUS  the corpus directory (default tests/data/large/cim_dist)
#   CIM_DIST_FETCH   0 to skip fetching; feeders not present are skipped
#
# Updates evals/validation/cim_dist/RESULTS.md with the sections of the legs
# it ran and exits nonzero when any case differs from its leg's expected file.

set -euo pipefail
cd "$(dirname "$0")/../../.."
here=evals/validation/cim_dist

legs=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
    case "$1" in
        census | cimgraph | schema) legs+=("$1") ;;
        *) echo "unknown leg: $1 (census, cimgraph, schema)" >&2; exit 2 ;;
    esac
    shift
done
[ $# -gt 0 ] && shift
[ ${#legs[@]} -eq 0 ] && legs=(census cimgraph schema)

venv="${CIM_VENV:-.venv-cim}"
if [ ! -d "$venv" ]; then
    python3 -m venv "$venv" 2>/dev/null || python -m venv "$venv"
fi
if [ -x "$venv/bin/python" ]; then
    py="$venv/bin/python"
else
    py="$venv/Scripts/python"
fi
"$py" -m pip install --quiet -r "$here/requirements-cim.txt"

corpus="${CIM_DIST_CORPUS:-tests/data/large/cim_dist}"
if [ "${CIM_DIST_FETCH:-1}" != 0 ]; then
    CIM_DIST_CORPUS="$corpus" PYTHON="$py" bash "$here/fetch_corpus.sh"
fi

powerio="${POWERIO:-target/release/powerio}"
if [ -z "${POWERIO:-}" ] && [ ! -x "$powerio" ] && [ ! -x "$powerio.exe" ]; then
    cargo build --release -p powerio-cli
fi

sections=$(mktemp -d)
trap 'rm -rf "$sections"' EXIT
status=0
reports=()
for leg in "${legs[@]}"; do
    case "$leg" in
        census) script=census.py ;;
        cimgraph) script=cimgraph_compare.py ;;
        schema) script=schema_check.py ;;
    esac
    echo "== $leg"
    "$py" "$here/$script" --powerio "$powerio" --corpus "$corpus" \
        --report "$sections/$leg.md" "$@" || status=1
    reports+=("$sections/$leg.md")
done
"$py" "$here/common.py" merge-results "$here/RESULTS.md" "${reports[@]}"
exit "$status"
