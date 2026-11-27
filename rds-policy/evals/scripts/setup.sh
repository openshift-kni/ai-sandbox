#!/usr/bin/env bash
# Store the model gateway key on the OpenShell gateway as a provider. Run it
# once per gateway, and again when the key or URL changes. run.sh attaches the
# provider, so sandboxes get a placeholder and never the key.
#
# export ANTHROPIC_BASE_URL=<model gateway url> ANTHROPIC_API_KEY=<key>
# export OPENSHELL_GATEWAY=<gateway>   # the openshell CLI reads this itself
# Set OPENSHELL_PROVIDER to name the provider, otherwise rds-model-gateway.
set -euo pipefail

evals=$(cd "$(dirname "$0")/.." && pwd)
provider=${OPENSHELL_PROVIDER:-rds-model-gateway}
profile_id=rds-model-gateway
: "${ANTHROPIC_BASE_URL:?set it to the model gateway URL}"
: "${ANTHROPIC_API_KEY:?set it to the model gateway key}"

# The CLI picks the profile format from the file extension.
dir=$(mktemp -d)
profile=$dir/$profile_id.yaml
trap 'rm -f "$profile" "$profile.new"; rmdir "$dir"' EXIT
host=${ANTHROPIC_BASE_URL#*://}
sed "s/GATEWAY_HOST/${host%%[:/]*}/" "$evals/openshell-provider.yaml" >"$profile"

# An update must carry the stored profile's resource_version.
if current=$(openshell provider profile export "$profile_id" 2>/dev/null); then
  { grep '^resource_version:' <<<"$current"; cat "$profile"; } >"$profile.new"
  mv "$profile.new" "$profile"
  openshell provider profile update --file "$profile" "$profile_id"
else
  openshell provider profile import --file "$profile"
fi

# A bare --credential name reads the key from the environment, so it never
# shows up on a command line.
if openshell provider get "$provider" >/dev/null 2>&1; then
  openshell provider update "$provider" --credential ANTHROPIC_API_KEY
else
  openshell provider create --name "$provider" --type "$profile_id" \
    --credential ANTHROPIC_API_KEY
fi
