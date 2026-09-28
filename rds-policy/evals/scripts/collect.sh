#!/usr/bin/env bash
# Download a sandbox's eval results into results/<sandbox>/.
# run.sh does this for you; use it by hand to retry a failed download.
#
# OPENSHELL_SANDBOX=<name> scripts/collect.sh
set -euo pipefail

name=${OPENSHELL_SANDBOX:?set it to the sandbox name}
evals=$(cd "$(dirname "$0")/.." && pwd)
workdir=/tmp/$(basename "$(cd "$evals/../.." && pwd)")/rds-policy/evals

openshell sandbox exec --name "$name" --no-tty --workdir "$workdir" -- make package-openshell-results

mkdir -p "$evals/results/$name"
openshell sandbox download "$name" /sandbox/rds-eval-results "$evals/results/$name"
ln -sfn "$name" "$evals/results/latest"

echo "Results: $evals/results/$name"
