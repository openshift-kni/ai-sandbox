#!/usr/bin/env bash
# One-time per gateway: store your local gcloud ADC there as a Vertex provider.
# Sandboxes attach it by name and only ever see a placeholder token, so no
# credential file is ever uploaded.
#
# export OPENSHELL_GATEWAY=<gateway>   # the openshell CLI reads this itself
# export VERTEX_AI_PROJECT_ID=<gcp project>
set -euo pipefail

openshell provider create --name "${OPENSHELL_PROVIDER:-rds-vertex}" \
  --type google-vertex-ai --from-gcloud-adc \
  --config VERTEX_AI_PROJECT_ID="${VERTEX_AI_PROJECT_ID:?set your GCP project id}" \
  --config VERTEX_AI_REGION="${VERTEX_AI_REGION:-global}"
