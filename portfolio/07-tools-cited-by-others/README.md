# 7. Tools cited by others: behaviorlock and agent-invariants

[← Back to overview](../README.md) · [Where they are cited](#where-they-are-cited) · [How to verify](#how-to-verify)

**Status: cited.** Two open-source projects point to two of my tools in their documentation; no usage is documented.

## Who they are

- **agent-proven** (MediaPlural), in its own words: "Full-suite verification and quality tooling for AI coding agents —
  every claim backed by evidence." ([repository](https://github.com/MediaPlural/agent-proven))
- **ContextOS**, in its own words: "Shared business limits for AI agents."
  ([repository](https://github.com/contextosai/ContextOS))

## Summary

The agent-regression skill of agent-proven points to behaviorlock for deterministic trace comparison, and ContextOS
lists agent-invariants among existing solutions in its landscape review. Both are pointers in documentation, not usage
reports.

## The tools

- [behaviorlock](https://github.com/christian140903-sudo/behaviorlock) (MIT): "Fails your CI when an agent's recorded
  behavior drifts after a model, prompt, memory, or tool change."
- [agent-invariants](https://github.com/christian140903-sudo/agent-invariants) (MIT): "Change the model, prompt,
  memory, or tools — without silently changing what your agent is allowed to do."

The tools are the delivery here; there is no separate `delivered/` folder.

## Where they are cited

1. **agent-proven**, agent-regression skill, since 2026-10-03
   ([`skills/agent-regression/SKILL.md` at commit `fe920e4`](https://github.com/MediaPlural/agent-proven/blob/fe920e4f0303bca837e43d6f6c40167aca7928b8/skills/agent-regression/SKILL.md)):

   > Deterministic trace comparison doesn't need reinventing:
   > [behaviorlock](https://github.com/christian140903-sudo/behaviorlock) takes recorded observations and contracts them
   > (sequence/set/rank/delta matchers, CI gate, SARIF).

2. **ContextOS**, research note, since 2026-10-22
   ([`docs/research/2026-10-22-value-proposition.md` at commit `ba5c41a`](https://github.com/contextosai/ContextOS/blob/ba5c41af785edb3cf940ac082739e69d5fdc6e00/docs/research/2026-10-22-value-proposition.md)),
   section "Evidence from the landscape", in a table of existing solutions. Its row for agent-invariants:

   > Deterministic trace rules, including evidence before completion.

   > Offline trace validation complements pre-dispatch reservation; neither should be presented as the other.

## Where my name appears

Only my GitHub account name, as part of the links; neither project names me otherwise.

## Timeline

| Date | Event |
|---|---|
| 2026-10-03 | agent-proven's agent-regression skill points to behaviorlock (commit `fe920e4`). |
| 2026-10-22 | ContextOS lists agent-invariants in its landscape review (commit `ba5c41a`). |

## Status

**Cited.** No usage documented.

## How to verify

Open the two documents linked above and search for "christian140903-sudo".

---

Last checked: 3 November 2026 · [← Back to overview](../README.md)
