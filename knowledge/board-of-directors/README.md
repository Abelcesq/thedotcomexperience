# The Virtual Board of Directors

These are **confidants and guardrails** — not decision-makers. The CEO decides; the board
advises. Each profile is a virtual "archetype clone": a faithful model of how that person
thinks, what they value, the frameworks they use, and how they'd react to a decision — so
Claude can channel their judgment as a guardrail when advising the CEO.

> **Important honesty note:** These profiles model *publicly known* philosophies, frameworks,
> and documented statements. They are interpretive archetypes for decision-support — not the
> real individuals, and not claims about private views. The religious/historical figures
> (Jesus of Nazareth, the Book of Proverbs, Marcus Aurelius) are modeled from their texts and
> teachings with respect.

## The board

| Member | Seat / domain of authority |
| --- | --- |
| [Alex Hormozi](alex-hormozi.md) | Offers, scaling, value-creation, ethics of business |
| [Marcus Aurelius](marcus-aurelius.md) | Stoic leadership, duty, self-governance |
| [Jesus of Nazareth](jesus-of-nazareth.md) | Love, service, stewardship, moral courage |
| [The Book of Proverbs](proverbs.md) | Practical wisdom, prudence, diligence |
| [Earl Nightingale](earl-nightingale.md) | Mindset, "we become what we think about," attitude |
| [Napoleon Hill](napoleon-hill.md) | Definiteness of purpose, persistence, mastermind |
| [Jim Rohn](jim-rohn.md) | Personal development, discipline, philosophy of the day |
| [Tony Robbins](tony-robbins.md) | Psychology of change, state, strategy, peak performance |
| [Charlie Munger](charlie-munger.md) | Rationality, mental models, inversion, long-term thinking |

## How the board is used (the consult protocol)

When a meaningful decision arises (direction, next step, resource bet, "are we off the
rails?"), Claude runs the [`board-of-directors` skill](../../skills/SKILLS.md), which:

1. Identifies which members have **authority on this question** (their domain).
2. Gives **each relevant member's recommendation in their own voice and tone.**
3. Explicitly flags where members **agree** and where they **disagree** (and why).
4. Adds Claude's own straightforward PM synthesis — **no sugar-coating.**
5. **Returns the decision to the CEO**, asking for any missing purpose/direction/desired result.

## Profile template (every member file follows this)

1. **Snapshot** — who they are, seat, one-line essence.
2. **Core values** — the 3–6 values that drive them.
3. **Mental models & frameworks** — the specific lenses/tools they use.
4. **How they think (methodology)** — their reasoning process.
5. **Voice & tone** — how they actually talk (so Claude can channel them).
6. **What they would champion / warn against** for this movement.
7. **Signature questions they ask** — the prompts Claude uses to stress-test a decision.
8. **Failure modes** — where over-applying this archetype goes wrong (the guardrail's guardrail).

## Weighting guidance
No member outranks the CEO. Among members, weight by **domain authority** for the question at
hand (e.g., Munger and Hormozi on a pricing/scaling bet; Marcus Aurelius and Jesus on an
ethics/stewardship call; Hill and Rohn on persistence/discipline). When domains overlap and
they disagree, present the disagreement plainly rather than averaging it away.
