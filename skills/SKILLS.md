# SKILLS.md — Skill Registry

The catalog of repeatable capabilities for The Dot Com Experience. Each skill is **defined
here** (what it does, success criteria, how it relates to others, gotchas) and **implemented**
as an invocable Claude Code skill under [`.claude/skills/`](../.claude/skills/).

> Framework note: this file is the `skills` pillar of the `knowledge · skills · projects`
> framework. When you add a skill, add it both here and in `.claude/skills/<name>/SKILL.md`.

---

## Skill: `board-of-directors`
- **Implementation:** [`.claude/skills/board-of-directors/SKILL.md`](../.claude/skills/board-of-directors/SKILL.md)
- **What it does:** Convenes the Virtual Board to advise on any meaningful decision; gives
  each relevant advisor's recommendation in their own voice; flags agreement/disagreement;
  runs an inversion pass; adds a no-sugar-coating PM synthesis; returns the decision to the CEO.
- **What success looks like:** The CEO receives a clear, honest, multi-perspective briefing
  with explicit agreements/disagreements and a recommended *furthest realistic step* — and is
  asked for the final decision. Stewardship/integrity risks are surfaced first.
- **Inputs:** the decision in one sentence; relevant `knowledge/` + `projects/` context; the
  options on the table.
- **Relates to:** Feeds `continuously-improve` (audits consult the board on recommendations).
  Reads all `knowledge/board-of-directors/*` profiles. Reports up to the CEO via `CLAUDE.md`'s
  chain of command.
- **Gotchas:** Don't convene all nine by reflex — select by domain authority, but always
  include a stewardship voice on weighty calls. Never let the board "decide." Don't average
  away genuine disagreement.

---

## Skill: `continuously-improve`
- **Implementation:** [`.claude/skills/continuously-improve/SKILL.md`](../.claude/skills/continuously-improve/SKILL.md)
- **What it does:** Runs a full audit of the container. **First re-reads every MD file** to
  rebuild context, then assesses knowledge/skills/projects for completeness, currency,
  coherence, and effectiveness, and writes a dated findings + recommendations report.
- **What success looks like:** Every MD file was actually read this run; findings are specific
  and cite paths; recommendations are prioritized and realistic; a dated audit file and the
  project dashboard are updated; drift from purpose is flagged first.
- **Inputs:** none required beyond repo access; optional focus area.
- **Relates to:** Consumes the entire `knowledge/`, `skills/`, and `projects/` trees. Invokes
  `board-of-directors` for any directional recommendation. Updates `projects/*/dashboard.md`.
- **Gotchas:** Never audit from memory. A missing referenced file is itself a finding. Keep
  the cadence (weekly light / monthly full / always before a launch).

---

## How skills communicate
- The **shared substrate is the file system**: skills read and write Markdown in
  `knowledge/`, `projects/`, and `skills/`. No skill holds private state — the repo is the
  single source of truth, so nothing is "missed, ignored, or unaccounted for."
- **`board-of-directors`** is the *decision* primitive; **`continuously-improve`** is the
  *audit* primitive that calls it. Both report upward to the CEO through the chain of command
  in `CLAUDE.md`.

## Planned skills (not yet built — see roadmap)
- `content-engine` — turn philosophy into on-voice posts/scripts at the brand bar.
- `command-center-sync` — keep the day/week/month task system and dashboard current.
- `brand-guardian` — check any artifact against `knowledge/brand/voice-and-themes.md`.
