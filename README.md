<h1 align="center">Christian Bucher</h1>

<p align="center"><strong>I direct AI coding agents to ship tested software — and I measure whether what I built actually worked.</strong></p>

<p align="center">Claude Code · MCP · evals · Vienna</p>

<p align="center">
  <strong>For teams:</strong> talks and workshops on running Claude Code — for engineering teams and for non-engineering teams that maintain their own skills.<br>
  <strong>Hiring me:</strong> looking for an AI engineering role focused on agent reliability — evals, agent tooling, MCP. Vienna or EU-remote, full-time. <a href="https://nextool.app/en/hire/">CV &amp; evidence</a>
</p>

<p align="center"><a href="https://nextool.app/en/">Website</a> · <a href="https://www.npmjs.com/~mr_bucher003">npm</a> · <a href="mailto:hello@nextool.app">hello@nextool.app</a></p>

---

## How I work with coding agents

Most of the code in my repositories was written by AI coding agents — mainly
Claude Code — under my direction. My part: I write the specification, set the
constraints (project instructions, hooks, permissions), decide what gets
tested, review the result and reject what does not hold. Release decisions and
every claim on this page are mine.

I also point agents at my own work. My rule since August 2026: before a number
or a plan is accepted, a separate review round with adversarial instructions
tries to break it. That round is how the withdrawn result under *Measurement*
was caught.

My setup is private for now. I have not yet run it inside an engineering team —
that is the job I am looking for.

## Evidence

Every test count comes with the command that reproduces it:

```bash
git clone https://github.com/christian140903-sudo/<repo> && cd <repo>
npm ci && npm test
```

| Failure it catches | Project | Tests (last run 2026-10-08, Node 22) |
|---|---|---|
| Agent memory that loses its history or keeps injected instructions as if they were facts | **[soul-mcp](https://github.com/christian140903-sudo/soul-mcp)** — memory server for MCP clients; quarantines injected instructions, records provenance; [on npm](https://www.npmjs.com/package/soul-mcp) | 374 passing |
| An agent reports `success: true`, but nothing changed | **[postcondition-mcp](https://github.com/christian140903-sudo/postcondition-mcp)** — checks whether the world changed, not whether the agent said so; [on npm](https://www.npmjs.com/package/postcondition-mcp) | 53 passing |
| A skill or agent behaves differently after a model update and nobody notices | **[behaviorlock](https://github.com/christian140903-sudo/behaviorlock)** — drift gate that compares recorded runs against contracts, without an LLM judge; referenced by [MediaPlural/agent-proven](https://github.com/MediaPlural/agent-proven) | 73 passing |
| A rule that must hold during an agent run is broken silently | **[agent-invariants](https://github.com/christian140903-sudo/agent-invariants)** — fail-closed checks for conditions that must stay true | 36 passing |
| A README or release claim with nothing behind it | **[proofspec](https://github.com/christian140903-sudo/proofspec)** — binds public claims to evidence contracts that run in CI | 74 passing |

Status, plainly: soul-mcp has had seven releases on npm since February 2026;
the other four are small v0.1 releases from July 2026. No external users are
documented for any of them yet. Passing tests establish only what they cover.

## Measurement

- **A null result from my own evidence inventory (Aug 2026):** plain runtime
  attachment without skills gave no quality gain on 20 tasks at 2.7× the cost
  (one model, descriptive); the skill effect is unmeasured. Raw artefacts not
  yet published.
- **A large effect I registered and withdrew the same day (Aug 2026), before
  it left the project:** the review round found a grader bug, which was
  fixable, and unequal format instructions between the two arms, which were
  not — so the experiment was discarded. One registered number I still cannot
  reproduce exactly from the stored answers.
  [Case study](https://nextool.app/en/case-study/) · raw data not yet published.

## Corrections

- **Oct 2026** — archived the February 2026 pages on nextool.app (an
  agent-generated tool farm and shop prototypes) and 384 promotional gists.
- **Aug 2026** — withdrew a benchmark number the same day it was registered
  (see *Measurement*).
- **Jul 2026** — withdrew a side project's launch claim of a "57–81 %"
  improvement: none of those figures is backed by the stored results. The one
  measurement showed +0.92 % on a self-defined score — a single run against a
  variant of the same system, with no significance test (ANIMA, now parked).
- **Jul 2026** — replaced a github.io page that contained invented client
  testimonials ([`4635f92`](https://github.com/christian140903-sudo/christian140903-sudo.github.io/commit/4635f92));
  that address now redirects to nextool.app.

## About

Self-taught, based in Vienna, no degree yet. I work full-time outside IT, in
sales and advisory work, and before that in truck dispatching — explaining
technical things to non-experts is my day job. I started building with Claude
Code in February 2026.

## Contact

[hello@nextool.app](mailto:hello@nextool.app) · [nextool.app](https://nextool.app/en/)

If a number on this page does not reproduce, please open an issue in that
repository.
