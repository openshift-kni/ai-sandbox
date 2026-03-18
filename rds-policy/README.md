# RDS Policy Agent

AI-driven policy generation for OpenShift RDS version updates. Helps telco
partners update Day 2 configuration policies when moving between OCP versions
(e.g. 4.18 to 4.20).

See [docs/DESIGN.md](docs/DESIGN.md) for the full design document.

## Skill

The agent's domain knowledge is packaged as an
[Agent Skill](https://agentskills.io) at
`rds_agent/skills/rds-policy-update/`.

### Using with Claude Code

Symlink the skill into `.claude/skills/` for auto-discovery:

```sh
mkdir -p .claude/skills
ln -s ../../rds_agent/skills/rds-policy-update .claude/skills/rds-policy-update
```

Then start Claude Code from this directory. The skill triggers on prompts
like "upgrade from 4.18 to 4.20" or "what changed between RDS versions".
