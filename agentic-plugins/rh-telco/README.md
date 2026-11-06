# Red Hat Telco agentic plugin

Skills for telco partners running the OpenShift RAN and Core reference
configurations. Both reference types are handled with the same skill,
`rds-policy-update`, which updates your Day 2 PolicyGenerator policies when
you move to a new OCP version, say 4.18 to 4.20.

**Persona**: Telco partner platform engineer (OpenShift RAN or Core)
**Marketplaces**: Lola, Claude Code

**AI-generated output requires expert human review.** This skill relies
on a large language model (LLM) to produce its results. LLMs can and do
make mistakes — including reasonable-looking output that is subtly wrong.
You **must** review all generated output (policies and other artifacts)
for correctness, completeness, accuracy, and suitability before applying
them to your environment. Do not deploy AI-generated configuration
without thorough expert human review.

**Data handling and privacy.** Any input provided to the skill —
including policy files, configuration data, cluster details, and Git
repository content — may be sent to the LLM for processing.

See the full
[disclaimer](https://github.com/openshift-kni/ai-sandbox/blob/main/rds-policy/README.md#important-security-privacy-and-disclaimer).

## Getting Started

The skill runs under Claude Code, the only environment we've tested so far.
You can install it with Lola or as a Claude Code plugin. The plugin adds a
validation hook that runs `kustomize build` on each PolicyGenerator file as
it's written, so the agent can fix errors right away. See
[HOOKS.md](https://github.com/openshift-kni/ai-sandbox/blob/main/rds-policy/docs/HOOKS.md).

The environment where the skill runs needs:

- `podman` with access to `registry.redhat.io`
- Read access to your policies, either:
  - a local copy
  - an authenticated Git repo with valid certificates (if your Git host uses
    internal certificates, add them to the trust store first)
- For the validation hook: `kustomize`, the PolicyGenerator plugin, and `jq`

Install with Lola, from your project:

```bash
lola market add rh-agentic-collections https://raw.githubusercontent.com/RHEcosystemAppEng/agentic-catalog/rc/v1.0.0/marketplace/rh-agentic-collection.yml
lola install rh-telco -a claude-code
```

Or install it as a Claude Code plugin:

```bash
claude plugin marketplace add 'RHEcosystemAppEng/agentic-catalog#rc/v1.0.0'
claude plugin install rh-telco@ecosystem-plugins
```

Then ask:

```
upgrade my policies from 4.18 to 4.20, the policy source is ./acme-ran
```

The skill first explains what changed between the two versions. When you
say go, it merges those changes into a copy of your policies, asking before
it copies anything and checking with you on each conflict. Your original
files stay untouched. The results land in
`/tmp/rds-merge-<target>-<timestamp>/`, along with a `checklist.md` showing
what happened to each CR. Review them and push them through your usual
process.

## Development

The source, design docs, and evals are in
[openshift-kni/ai-sandbox](https://github.com/openshift-kni/ai-sandbox).
To test local changes:

```bash
claude --plugin-dir /path/to/ai-sandbox/agentic-plugins/rh-telco
```
