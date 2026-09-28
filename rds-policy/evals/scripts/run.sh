#!/usr/bin/env bash
# Run the eval in a fresh OpenShell sandbox: create, upload, run Promptfoo,
# download the results, delete the sandbox. Exits with the eval's own code.
#
# export OPENSHELL_GATEWAY=<gateway>   # the openshell CLI reads this itself
# Set OPENSHELL_SANDBOX to name the sandbox, otherwise rds-<MMDD-HHMMSS>.
# Set PROMPTFOO_EVAL_ARGS='--filter-first-n 1' for a one-test smoke run.
# Set OPENSHELL_IMAGE to override the sandbox image (default: the community
# `base`, which ships uv, Python 3.14 and node already).
# Set OPENSHELL_KEEP=1 to keep the sandbox after collecting, to look around in it.
set -euo pipefail

here=$(dirname "$0")
evals=$(cd "$here/.." && pwd)
repo=$(cd "$evals/../.." && pwd)
name=${OPENSHELL_SANDBOX:-rds-$(date +%m%d-%H%M%S)}
workdir=/tmp/$(basename "$repo")/rds-policy/evals
provider=${OPENSHELL_PROVIDER:-rds-vertex}
image=${OPENSHELL_IMAGE:-base}

[ "${#name}" -le 19 ] || {
  echo "sandbox name '$name' is over 19 characters" >&2
  exit 1
}

# Env set at create is visible to every later exec, so the commands below do not
# repeat it. CLAUDE_CODE_SKIP_VERTEX_AUTH makes the agent send the provider's
# placeholder token; the sandbox proxy swaps in the real credential.
openshell sandbox create --name "$name" --provider "$provider" --from "$image" \
  --no-auto-providers \
  --upload "$repo:/tmp" \
  --policy "$evals/openshell-policy.yaml" \
  --env CLAUDE_CODE_USE_VERTEX=1 --env CLAUDE_CODE_SKIP_VERTEX_AUTH=1 \
  --env SANDBOX_RESULTS_DIR=/sandbox/rds-eval-results \
  --no-tty --detach

# Detached, because an attached exec stream is cut by the route's idle timeout
# after about a minute of silence. The pid file is what the poll below reads.
# shellcheck disable=SC2016
openshell sandbox exec --name "$name" --no-tty --workdir "$workdir" \
  --env PROMPTFOO_EVAL_ARGS="${PROMPTFOO_EVAL_ARGS:-}" \
  --env PROMPTFOO_CONCURRENCY="${PROMPTFOO_CONCURRENCY:-3}" \
  -- sh -lc 'unset VIRTUAL_ENV; mkdir -p "$SANDBOX_RESULTS_DIR"; nohup make eval-openshell-recorded >/dev/null 2>&1 </dev/null & echo $! >"$SANDBOX_RESULTS_DIR/pid"; echo "eval started (pid $!)"' || {
  OPENSHELL_SANDBOX=$name "$here/clean.sh"
  exit 1
}

# Poll until it finishes. An occasional empty answer is a gateway blip, so allow
# a few misses rather than treating one bad answer as a dead eval.
# shellcheck disable=SC2016
check='d=/sandbox/rds-eval-results; if [ -f "$d/exit-code" ]; then echo "finished:$(cat "$d/exit-code")"; elif [ -f "$d/pid" ] && kill -0 "$(cat "$d/pid")" 2>/dev/null; then echo running; else echo missing; fi'
status=
misses=0
while [ -z "$status" ]; do
  state=$(openshell sandbox exec --name "$name" --no-tty -- sh -c "$check" 2>/dev/null || true)
  case $state in
    running)
      misses=0
      printf '.'
      sleep 15
      ;;
    finished:*)
      status=${state#finished:}
      printf '\nEval finished with exit %s\n' "$status"
      ;;
    *)
      misses=$((misses + 1))
      [ "$misses" -lt 10 ] || {
        echo "no status from $name after $misses polls (last: '$state'); sandbox kept" >&2
        exit 1
      }
      printf '?'
      sleep 15
      ;;
  esac
done

OPENSHELL_SANDBOX=$name "$here/collect.sh" || {
  echo "results not collected; $name kept. Retry: OPENSHELL_SANDBOX=$name scripts/collect.sh" >&2
  exit 1
}
if [ -n "${OPENSHELL_KEEP:-}" ]; then
  echo "$name kept. Delete it with: OPENSHELL_SANDBOX=$name scripts/clean.sh"
else
  OPENSHELL_SANDBOX=$name "$here/clean.sh"
fi
exit "$status"
