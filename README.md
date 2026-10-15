<h1 align="center">Christian Bucher</h1>

<p align="center"><strong>I direct AI coding agents to ship tested software — and I measure whether what I build actually works.</strong></p>

<p align="center">Claude Code · MCP · evals · Vienna</p>

<p align="center"><a href="https://www.npmjs.com/~mr_bucher003">npm</a></p>

---

## How I work with coding agents

Most of the code in my repositories was written by AI coding agents — mainly
Claude Code — under my direction. My part: I write the specification, set the
constraints (project instructions, hooks, permissions), decide what gets
tested, review the result and reject what does not hold. Release decisions and
every claim on this page are mine.

Before a number or a plan is accepted, a separate review round with adversarial
instructions tries to break it; that is how the withdrawn result under
*Measurement* was caught. I have not yet run this setup inside an engineering
team — that is the job I am looking for.

## Evidence

Every test count comes with the command that reproduces it:

```bash
git clone https://github.com/christian140903-sudo/<repo> && cd <repo>
npm ci && npm test
```

| Failure it catches | Project | Tests (Node 22, fresh clone) |
|---|---|---|
| Agent memory that loses its history or keeps injected instructions as if they were facts | **[soul-mcp](https://github.com/christian140903-sudo/soul-mcp)** — memory server for MCP clients; quarantines injected instructions, records provenance; [on npm](https://www.npmjs.com/package/soul-mcp) | 374 passing (last verified 2026-10-08) |
| An agent reports `success: true`, but nothing changed | **[postcondition-mcp](https://github.com/christian140903-sudo/postcondition-mcp)** — checks whether the world changed, not whether the agent said so; [on npm](https://www.npmjs.com/package/postcondition-mcp) | 55 passing (last verified 2026-10-09) |
| A skill or agent behaves differently after a model update and nobody notices | **[behaviorlock](https://github.com/christian140903-sudo/behaviorlock)** — drift gate that compares recorded runs against contracts, without an LLM judge | 73 passing (last verified 2026-10-08) |
| A rule that must hold during an agent run is broken silently | **[agent-invariants](https://github.com/christian140903-sudo/agent-invariants)** — fail-closed checks for conditions that must stay true | 36 passing (last verified 2026-10-08) |

Referenced by [MediaPlural/agent-proven](https://github.com/MediaPlural/agent-proven)
(its `agent-regression` skill points to behaviorlock) — a pointer in another
project's documentation, not a usage report.

Status, plainly: built since February 2026, next to a full-time job outside IT.
soul-mcp is on npm (current release 4.0.2); postcondition-mcp, behaviorlock and
agent-invariants are small v0.1 releases from July 2026. No external users are
documented for any of them yet.
Passing tests establish only what they cover.

## Measurement

- **Two flaws found in my own evaluation harness (Aug 2026):** a grader bug,
  which was fixable, and unequal format instructions between the two arms,
  which were not. I withdrew the registered result the same day, before it
  left the project, and discarded the experiment. One registered number I
  still cannot reproduce exactly from the stored answers. Raw data not yet
  published.
- **A null result from my own evidence inventory (Aug 2026):** plain runtime
  attachment without skills gave no quality gain on 20 tasks at 2.7× the cost
  (one model, descriptive); the skill effect is unmeasured. Raw artefacts not
  yet published.

## Corrections

Earlier experiments (Feb–Sep 2026) are archived; details on request.

## About

Self-taught, based in Vienna. I work full-time outside IT, in sales and
advisory work, and before that in dispatching — explaining technical things to
non-experts is my day job. I started building with Claude Code in February
2026.

## Contact

If a number on this page does not reproduce, please open an issue in that
repository.
