---
name: continuously-improve
description: Run a regular audit of the whole project container. Use when asked to audit, review status, find what's missing/stale, or recommend improvements. The skill first re-reads every Markdown file to rebuild full context, then assesses the state of knowledge/skills/projects against purpose, and produces a findings + recommendations report. No sugar-coating.
---

# Continuously Improve — Audit Skill

The standing auditor for **The Dot Com Experience** container. Its job: rebuild context from
the source of truth (the MD files), then assess honestly what is working, what is stale,
what is missing, and what to do next — measured against the project's stated purpose.

## Operating principle
Context first, judgment second. **Never audit from memory** — re-read the files. The
container changes; your prior context is stale by definition.

## Procedure

### 1. Rebuild context (read everything)
Read, in this order:
1. `CLAUDE.md` (the operating contract)
2. All of `knowledge/` — especially `about-me/`, `project-purpose/`, `brand/`, and every
   `board-of-directors/*.md`
3. `skills/SKILLS.md` and each `.claude/skills/*/SKILL.md`
4. Each `projects/*/PROJECT.md`, `clarity.md`, `roadmap.md`, `command-center.md`, `dashboard.md`

Use a fast file-discovery sweep so nothing is missed (e.g. find all `*.md`). If a referenced
file is missing, that is itself a finding.

### 2. Assess against the framework: knowledge · skills · projects
For each pillar, evaluate:
- **Completeness** — are required files present and filled in (no orphan `[TODO: CEO]`s that
  block progress)?
- **Currency** — is anything stale, contradicted by newer info, or out of date?
- **Coherence** — do the pieces agree with each other and with the stated purpose/voice?
- **Effectiveness** — for skills: do they have clear success criteria and do they actually
  get used? For projects: is the dashboard current and the roadmap realistic?

### 3. Consult the board where judgment is needed
For any recommendation involving direction or a real bet, invoke the `board-of-directors`
skill rather than ruling solo.

### 4. Produce the audit report
Write findings to `projects/<project>/audits/AUDIT-<YYYY-MM-DD>.md` (create the `audits/`
folder if absent) and update `dashboard.md`. Then summarize to the CEO.

## Report format
```
# Audit — <date>
## 1. Context snapshot (what state the container is in)
## 2. Findings
   - 🟢 Working well
   - 🟡 Needs attention (stale / incomplete / incoherent)
   - 🔴 Blocking or broken / drifting from purpose
## 3. Gaps & missing pieces
## 4. Recommendations (prioritized, with the furthest realistic next step)
## 5. Questions for the CEO
```

## Success criteria (what a good audit looks like)
- Every MD file was actually read this run (not assumed).
- Findings are specific and cite file paths.
- Recommendations are prioritized and honest about what's realistic now vs. later.
- The dashboard and a dated audit file are updated.
- No sugar-coating; drift from purpose or stewardship is flagged first.

## Cadence
Recommended: a light audit weekly, a full audit monthly, and always before a major decision
or launch. (A scheduled/automated cadence can be wired up later — see roadmap Phase: tooling.)
