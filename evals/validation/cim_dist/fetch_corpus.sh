#!/usr/bin/env bash
# Leg A of the distribution CIM validation: fetch the corpus feeders that
# manifest.toml names into tests/data/large/cim_dist/ (gitignored, kept out
# of the repo) and check each one's SHA-256. A feeder already present with
# the right digest is kept; a digest mismatch fails the run.
#
#   bash evals/validation/cim_dist/fetch_corpus.sh
#
# Environment:
#   CIM_DIST_CORPUS  the directory to fetch into (default tests/data/large/cim_dist)
#   PYTHON           a Python 3.11+ to read the manifest (default python3, then python)

set -euo pipefail
cd "$(dirname "$0")/../../.."

dir="${CIM_DIST_CORPUS:-tests/data/large/cim_dist}"
py="${PYTHON:-}"
if [ -z "$py" ]; then
    # The first that runs and has tomllib (Windows has a python3 stub that
    # does neither).
    for candidate in python3 python; do
        if "$candidate" -c 'import tomllib' 2>/dev/null; then
            py="$candidate"
            break
        fi
    done
fi
if [ -z "$py" ]; then
    echo "fetch_corpus.sh needs Python 3.11 or later (set PYTHON)" >&2
    exit 1
fi
mkdir -p "$dir"

digest() {
    if command -v sha256sum >/dev/null; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# One "file url sha256" line per feeder (without the \r a Windows Python
# ends lines with).
feeders=$("$py" -c '
import sys
sys.path.insert(0, "evals/validation/cim_dist")
import common
for f in common.corpus_feeders():
    print(f.file, f.url, f.sha256)
' | tr -d '\r')

status=0
while read -r file url sha; do
    path="$dir/$file"
    if [ -f "$path" ] && [ "$(digest "$path")" = "$sha" ]; then
        echo "have $file"
        continue
    fi
    curl -fsSL "$url" -o "$path.part"
    got=$(digest "$path.part")
    if [ "$got" != "$sha" ]; then
        echo "FAIL $file: sha256 $got, manifest says $sha" >&2
        rm -f "$path.part"
        status=1
        continue
    fi
    mv "$path.part" "$path"
    echo "fetched $file"
done <<< "$feeders"
exit "$status"
