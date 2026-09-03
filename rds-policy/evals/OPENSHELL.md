# Run the eval in OpenShell

This creates a confined OpenShell sandbox, installs the eval dependencies, and
runs Promptfoo inside the sandbox. The agent and grader use separate Vertex
models, so the policy allows direct Vertex access instead of using OpenShell's
single-model inference router.

## Prerequisites

- A running OpenShell gateway and access to its Kubernetes namespace
- `openshell` and `oc` configured locally
- Google Cloud Application Default Credentials (ADC) with Vertex access

Set the values for your environment:

```sh
export GW=k8s-poc
export NS=openshell-poc
export NAME=eval1
export GCP_PROJECT=your-project
export GCP_REGION=global
```

If the gateway is not already reachable, keep this running in another terminal:

```sh
oc port-forward -n "$NS" pod/openshell-0 18090:8080
```

## Create and prepare the sandbox

Run this from the repository root:

```sh
openshell -g "$GW" sandbox create --name "$NAME" --no-tty \
  --env HOME=/tmp \
  --env CLAUDE_CODE_USE_VERTEX=1 \
  --env ANTHROPIC_VERTEX_PROJECT_ID="$GCP_PROJECT" \
  --env CLOUD_ML_REGION="$GCP_REGION" \
  --env GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json \
  --env UV_PYTHON_DOWNLOADS=never \
  --policy rds-policy/evals/openshell-policy.yaml \
  -- sleep infinity </dev/null &
```

Apply the cluster DNS workaround, recreate the pod, and wait for it to become
ready:

```sh
oc patch sandbox "default--$NAME" -n "$NS" --type=json -p \
  '[{"op":"add","path":"/spec/podTemplate/spec/dnsConfig","value":{"options":[{"name":"ndots","value":"1"}]}}]'
oc delete pod "default--$NAME" -n "$NS"
oc wait --for=condition=Ready pod/"default--$NAME" -n "$NS" --timeout=5m
```

Copy local ADC after recreating the pod because `/tmp` is ephemeral:

```sh
oc cp ~/.config/gcloud/application_default_credentials.json \
  "$NS/default--$NAME:/tmp/adc.json" -c agent
oc exec -n "$NS" "default--$NAME" -c agent -- chmod 0644 /tmp/adc.json
```

This ADC copy is the currently verified interim setup. It places a plaintext
credential in the sandbox; use a dedicated credential and delete the sandbox
when the run is complete.

## Run the eval

Use `openshell sandbox exec`, not `oc exec`, so the filesystem and network
policy remains enforced:

```sh
openshell -g "$GW" sandbox exec --name "$NAME" --no-tty -- bash -lc '
  set -eu
  git clone -q https://github.com/openshift-kni/ai-sandbox /tmp/ai-sandbox
  cd /tmp/ai-sandbox/rds-policy/evals
  make setup
  npx promptfoo eval --no-cache --filter-first-n 1
' </dev/null
```

The final command runs one test as a smoke check. Run the full suite afterward:

```sh
openshell -g "$GW" sandbox exec --name "$NAME" --no-tty -- \
  bash -lc 'cd /tmp/ai-sandbox/rds-policy/evals && make eval' </dev/null
```

Promptfoo stores results in `/tmp/.promptfoo/promptfoo.db`. OpenShell audit logs
are available with:

```sh
openshell -g "$GW" logs "$NAME" --source sandbox -n 400
```

Delete the credential-bearing sandbox when finished:

```sh
openshell -g "$GW" sandbox delete "$NAME"
```
