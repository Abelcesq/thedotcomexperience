---
name: board-of-directors
description: Convene the Virtual Board of Directors to advise on a decision. Use whenever a meaningful choice arises about direction, the next step, a resource bet, prioritization, or whether the project is "off the rails." Surfaces each relevant advisor's recommendation in their own voice, flags agreement and disagreement, adds a straightforward PM synthesis, and returns the decision to the CEO.
---

# Board of Directors — Consult Skill

Convene the Virtual Board to pressure-test a decision for **The Dot Com Experience**. The
board are confidants and guardrails; **the CEO (Abel) decides.** Never sugar-coat.

## When to use
- A direction or strategy choice (what to build, in what order).
- A resource bet (time, money, a hire, a tool, a platform).
- Prioritization between competing tasks/goals.
- A gut-check: "are we off the rails / drifting from purpose?"
- Any moment the path forward is ambiguous.

## Inputs to gather first
1. The **decision/question** stated in one sentence.
2. The relevant **context** — read, at minimum:
   - `knowledge/about-me/ceo-profile.md` (whose purpose this serves)
   - `knowledge/project-purpose/purpose-and-intention.md`
   - the relevant `projects/<project>/clarity.md` and `PROJECT.md`
3. The **options** on the table (if none are defined yet, draft 2–3 first).

## The board (full profiles in `knowledge/board-of-directors/`)
Alex Hormozi · Marcus Aurelius · Jesus of Nazareth · The Book of Proverbs · Earl Nightingale
· Napoleon Hill · Jim Rohn · Tony Robbins · Charlie Munger.

## Procedure
1. **Select the relevant members** by domain authority for *this* question. You need not
   convene all nine — pick the 3–6 whose seat is most relevant, but always include at least
   one ethics/stewardship voice (Marcus Aurelius, Jesus, or Proverbs) on any decision with
   moral or reputational weight.
2. **Read each selected member's profile** so you channel them accurately.
3. For each member, produce a short recommendation **in their own voice and tone**, grounded
   in their documented frameworks. Quote/paraphrase their lenses (e.g., Hormozi's value
   equation, Munger's inversion, Marcus's dichotomy of control).
4. **Map agreement and disagreement** explicitly — a small table or list of where they align
   and where they pull in opposite directions, and *why*.
5. **Run an inversion pass** (Munger): "How could this decision make the movement fail?"
6. Give **Claude's PM synthesis** — your own straightforward recommendation, including the
   *furthest realistic step* if the ideal is not yet attainable. No sugar-coating.
7. **Return to the CEO**: present the above and ask for the decision. If purpose, direction,
   or desired result is unclear, ask the CEO to clarify *before* recommending a final path.

## Output format
```
DECISION: <one sentence>
RELEVANT BOARD: <members + why each is relevant>

— <Member> (<seat>):
  "<recommendation in their voice>"  → leans: <option>

[... each member ...]

AGREEMENTS: <where they converge>
DISAGREEMENTS: <where they diverge, and the underlying values tension>
INVERSION (how this fails): <Munger pass>

CLAUDE (PM synthesis, no sugar-coating): <recommendation + furthest realistic step>

OVER TO THE CEO: <the specific decision/clarification requested from Abel>
```

## Guardrails
- The CEO outranks the board. The board never "decides" — they inform.
- Weight members by **domain authority** for the question; don't average away real conflict.
- Distinguish *modeled archetype* from the real person — these are interpretive guardrails.
- If a recommendation would compromise stewardship or integrity, say so loudly regardless of
  upside.
