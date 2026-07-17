<h1 align="center">Christian Bucher</h1>

<p align="center"><strong>I build the trust layer around AI agents.</strong></p>

<p align="center">
  Memory with provenance · independent outcome checks · executable claims · behavior compatibility
</p>

<p align="center">
  <a href="https://nextool.app">NexTool</a> ·
  <a href="https://nextool.app/docs/">Product docs</a> ·
  <a href="https://www.npmjs.com/~mr_bucher003">npm</a> ·
  <a href="mailto:hello@nextool.app">Contact</a>
</p>

---

## One stack. Six narrow jobs.

Most agent systems make it easy to call a tool. My open-source work focuses on
the harder questions that come next: Why did the agent decide this? Did the
outside world actually change? Is the public claim supported? Did an upgrade
silently alter behavior? Did a critical rule remain true?

| Failure to prevent | Project | Public evidence |
|---|---|---|
| Lost context and provenance | **[Soul MCP](https://github.com/christian140903-sudo/soul-mcp)** | npm · 23 MCP tools · 358 tests |
| Tool success without real outcome | **[Postcondition](https://github.com/christian140903-sudo/postcondition-mcp)** | npm · MCP + SDK + CLI · 53 tests |
| Unsupported README or release claims | **[Proofspec](https://github.com/christian140903-sudo/proofspec)** | source release · five reports · 70 tests |
| Silent behavior drift after an upgrade | **[Behaviorlock](https://github.com/christian140903-sudo/behaviorlock)** | source release · nine matchers · 73 tests |
| Critical runtime conditions going unproved | **[Agent Invariants](https://github.com/christian140903-sudo/agent-invariants)** | source release · fail-closed policies · 36 tests |
| Opaque, disposable cognitive state | **[ANIMA Kernel](https://github.com/christian140903-sudo/anima)** | source release · zero runtime dependencies · 446 tests |

```text
intent
  ↓
Soul ── remembers decisions, provenance, corrections, and outcomes
  ↓
Agent Invariants ── checks what must remain true during execution
  ↓
Postcondition ── observes whether the intended world state exists
  ↓
Proofspec ── binds public claims to narrow evidence contracts

Behaviorlock ── compares observable behavior before and after upgrades
```

These projects can work together, but none pretends to be the whole agent
stack. Each has a narrow promise, tests for that promise, a security or evidence
boundary, and an honest `unknown` state where the software cannot prove enough.

## Start with the failure you need to prevent

### Soul MCP — continuity with provenance

[![npm](https://img.shields.io/npm/v/soul-mcp?style=flat-square&label=npm&color=5de4a8)](https://www.npmjs.com/package/soul-mcp)
[![downloads](https://img.shields.io/npm/dw/soul-mcp?style=flat-square&label=weekly%20downloads&color=54d8ff)](https://www.npmjs.com/package/soul-mcp)
[![CI](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/soul-mcp/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/christian140903-sudo/soul-mcp/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/soul-mcp?style=flat-square)](https://github.com/christian140903-sudo/soul-mcp/blob/main/LICENSE)

Local-first agent memory with durable runs, receipts, episodes, conflicts,
calibration, deliberation, and a governed skill registry.

```bash
claude mcp add soul -- npx -y soul-mcp
```

**[Product guide](https://nextool.app/soul/)** ·
**[Source](https://github.com/christian140903-sudo/soul-mcp)** ·
**[npm](https://www.npmjs.com/package/soul-mcp)**

### Postcondition — outcome verification after tools return

[![npm](https://img.shields.io/npm/v/postcondition-mcp?style=flat-square&label=npm&color=5de4a8)](https://www.npmjs.com/package/postcondition-mcp)
[![downloads](https://img.shields.io/npm/dw/postcondition-mcp?style=flat-square&label=weekly%20downloads&color=54d8ff)](https://www.npmjs.com/package/postcondition-mcp)
[![CI](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/postcondition-mcp/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/christian140903-sudo/postcondition-mcp/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/postcondition-mcp?style=flat-square)](https://github.com/christian140903-sudo/postcondition-mcp/blob/main/LICENSE)

Declare an intended result, observe constrained file, HTTP, Git, npm, or manual
evidence, and retain an honestly classified receipt instead of trusting
`success: true`.

```bash
npx -y postcondition-mcp serve
```

**[Product guide](https://nextool.app/postcondition/)** ·
**[Source](https://github.com/christian140903-sudo/postcondition-mcp)** ·
**[npm](https://www.npmjs.com/package/postcondition-mcp)**

### Proofspec — executable public claims

[![release](https://img.shields.io/github/v/release/christian140903-sudo/proofspec?style=flat-square&color=54d8ff)](https://github.com/christian140903-sudo/proofspec/releases/tag/v0.1.0)
[![CI](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/proofspec/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/christian140903-sudo/proofspec/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/proofspec?style=flat-square)](https://github.com/christian140903-sudo/proofspec/blob/main/LICENSE)

Turn README, product, benchmark, and release claims into versioned evidence
contracts with dependencies, policies, receipts, CI gates, and JSON, Markdown,
HTML, SARIF, and JUnit reports.

**[Product guide](https://nextool.app/proofspec/)** ·
**[Source](https://github.com/christian140903-sudo/proofspec)** ·
**[v0.1.0 release](https://github.com/christian140903-sudo/proofspec/releases/tag/v0.1.0)**

### Behaviorlock — observable compatibility across agent upgrades

[![release](https://img.shields.io/github/v/release/christian140903-sudo/behaviorlock?style=flat-square&color=54d8ff)](https://github.com/christian140903-sudo/behaviorlock/releases/tag/v0.1.0)
[![CI](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/behaviorlock/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/christian140903-sudo/behaviorlock/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/behaviorlock?style=flat-square)](https://github.com/christian140903-sudo/behaviorlock/blob/main/LICENSE)

Compare portable before-and-after traces with deterministic contracts for tool
sequences, permissions, output structure, outcomes, ranks, sets, and bounded
metrics — without provider calls or an LLM judge.

**[Product guide](https://nextool.app/behaviorlock/)** ·
**[Source](https://github.com/christian140903-sudo/behaviorlock)** ·
**[v0.1.0 release](https://github.com/christian140903-sudo/behaviorlock/releases/tag/v0.1.0)**

## Public proof, not audience theater

I do not use fake adoption numbers or turn test counts into a claim of product
quality. These are narrow, inspectable facts about the current public surfaces:

| Surface | Current public fact |
|---|---|
| Soul MCP | 358 automated tests; CI on Node 20, 22, and 24 |
| Postcondition | 53 automated tests; clean-install and MCP handshake checks |
| Proofspec | 70 automated tests; 98.05% line coverage; five report formats |
| Behaviorlock | 73 automated tests; 99.06% line coverage; nine deterministic matchers |
| Agent Invariants | 36 automated tests; source release and CI |
| ANIMA Kernel | 446 automated tests; zero runtime dependencies |
| [NexTool](https://nextool.app) | 269 browser-tool pages; 131 technical guides; static site audit in CI |

Passing tests establish only what they cover. Hash chains are not signatures.
Portable traces are not provenance attestations. A green compatibility gate
covers only declared scenarios. Those boundaries live beside the product claims,
not in fine print after them.

## The larger system

I also run **Miguel**, a private personal AI operating layer that connects
memory, voice, multiple model providers, tools, and long-running local services.
It is the laboratory from which reusable mechanisms are extracted — not a
50,000-line personal monolith I intend to dump online. Private conversations,
identity state, credentials, machine paths, and raw session history stay private.

The public products are rebuilt as small, documented, testable systems with
portable schemas and explicit security boundaries.

## How I build

I use capable models as research, coding, review, and testing collaborators. I
choose the architecture, resolve conflicts, validate results, manage releases,
and remain responsible for every public claim.

My default loop is:

```text
define the failure → design the evidence → build → falsify → ship → observe
```

<p align="center"><strong>Inspect the source. Run the tests. Judge the boundary.</strong></p>
