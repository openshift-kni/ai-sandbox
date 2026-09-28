#!/usr/bin/env bash
# Delete a sandbox. Collect first; deleting discards the results.
#
# OPENSHELL_SANDBOX=<name> scripts/clean.sh
set -euo pipefail

openshell sandbox delete "${OPENSHELL_SANDBOX:?set it to the sandbox name}"
