<h1 align="center">Christian Bucher</h1>

<p align="center"><strong>I build systems that give AI memory, tools, and proof of outcome.</strong></p>

<p align="center">
  AI systems builder in Vienna · evidence-first · open source
</p>

<p align="center">
  <a href="https://christian140903-sudo.github.io/">Portfolio</a> ·
  <a href="https://www.npmjs.com/~mr_bucher003">npm</a> ·
  <a href="https://nextool.app">NexTool</a> ·
  <a href="mailto:christian140903@gmail.com">Email</a>
</p>

---

## The trust stack

Most agent systems stop when a tool returns `success`. Mine separate what the
agent intended, what it remembers, what it executed, and what the outside world
actually shows.

| Layer | System | What it makes inspectable |
|---|---|---|
| Continuity | **[Soul MCP](https://github.com/christian140903-sudo/soul-mcp)** | Why a decision exists: memory, provenance, goals, corrections, receipts |
| Outcome | **[Postcondition](https://github.com/christian140903-sudo/postcondition-mcp)** | Whether the intended world state exists: independent checks and hash-chained observations |

```text
intent → action → independent observation → satisfied / violated / unknown
```

### Soul MCP

[![npm version](https://img.shields.io/npm/v/soul-mcp?style=flat-square&color=c98a3a)](https://www.npmjs.com/package/soul-mcp)
[![npm downloads](https://img.shields.io/npm/dw/soul-mcp?style=flat-square&color=2d8b92)](https://www.npmjs.com/package/soul-mcp)
[![tests](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/soul-mcp/ci.yml?branch=main&style=flat-square&label=tests)](https://github.com/christian140903-sudo/soul-mcp/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/soul-mcp?style=flat-square)](https://github.com/christian140903-sudo/soul-mcp/blob/main/LICENSE)

**[Soul MCP](https://github.com/christian140903-sudo/soul-mcp)** is a local-first, trust-aware runtime for decisions, memory, skills, and verifiable outcomes. It connects to MCP-compatible AI clients without requiring a cloud account.

```bash
claude mcp add soul -- npx -y soul-mcp
```

Current public evidence: **23 MCP tools · 358 tests · MIT · zero required cloud services**.

### Postcondition

[![npm version](https://img.shields.io/npm/v/postcondition-mcp?style=flat-square&color=c98a3a)](https://www.npmjs.com/package/postcondition-mcp)
[![npm downloads](https://img.shields.io/npm/dw/postcondition-mcp?style=flat-square&color=2d8b92)](https://www.npmjs.com/package/postcondition-mcp)
[![tests](https://img.shields.io/github/actions/workflow/status/christian140903-sudo/postcondition-mcp/ci.yml?branch=main&style=flat-square&label=tests)](https://github.com/christian140903-sudo/postcondition-mcp/actions)
[![license](https://img.shields.io/github/license/christian140903-sudo/postcondition-mcp?style=flat-square)](https://github.com/christian140903-sudo/postcondition-mcp/blob/main/LICENSE)

**[Postcondition](https://github.com/christian140903-sudo/postcondition-mcp)** is outcome verification for AI agents. It declares a testable result, observes file, HTTP, Git, or npm state through constrained read-only verifiers, and never disguises self-attestation as external proof.

```bash
npx -y postcondition-mcp serve
```

Current public evidence: **MCP + SDK + CLI · 53 tests · Node 20/22/24 · MIT · zero known production dependency vulnerabilities**.

## Systems

| System | What it is | Evidence / state |
|---|---|---|
| **[Soul MCP](https://github.com/christian140903-sudo/soul-mcp)** | A runtime for accountable AI memory and decisions | npm · 358 tests · public |
| **[Postcondition](https://github.com/christian140903-sudo/postcondition-mcp)** | Outcome verification for agents after tools return | npm · 53 tests · public |
| **[NexTool](https://nextool.app)** | A practical library of browser-based tools and technical guides | 260+ tools · 132 articles · live |
| **[Anima](https://github.com/christian140903-sudo/anima)** | A Python kernel for testable system logic and behavioral guarantees | 446 tests · public source |
| **[Miguel](https://christian140903-sudo.github.io/#miguel)** | A personal AI operating layer connecting memory, voice, models, and tools | 128 API endpoints · system case study |

## How I work

I use several AI models as a coordinated engineering team. My work is the architecture around them: framing the objective, assigning the work, judging trade-offs, testing the result, and owning the release.

My default loop is simple:

`decision → execution → evidence → outcome → learning`

I separate what is **public**, what is **running**, and what is still a **candidate**. Claims should be inspectable; unfinished ideas should not masquerade as products.

## Current direction

I am turning a larger reservoir of working experiments into a smaller family of useful, installable systems around **outcome-verified autonomy**. Soul holds continuity; Postcondition checks reality. Model routing, behavioural drift, claim-to-evidence CI, learning validation, and voice/tool interfaces are promoted only when they strengthen that story and pass code, licensing, privacy, tests, and real-use review.

<p align="center"><em>Inspect the code. Run the tests. Judge the outcome.</em></p>
