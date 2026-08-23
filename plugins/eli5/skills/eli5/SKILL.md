---
name: eli5
description: >
  Explain something in plain language without dumbing it down. Use when the user asks to
  explain, "ELI5", "explain like I'm 5", "in plain English", "break this down", "what even
  is X", "how does X actually work", "I don't understand X", or asks for a version they can
  give a client, a homeowner, a crew, a lender, or a new hire. Produces a working mental
  model: the problem, the idea, the steps in order, the one-line model to remember, and the
  part people usually get wrong. Not for code walkthroughs or API docs where the user wants
  full technical depth — explain those directly instead.
---

# Explain It Simply

Your job is to make someone genuinely understand something they didn't understand before.
That is a higher bar than making it sound simple.

"ELI5" is a request for **clarity, not condescension**. Nobody wants baby talk. They want
the jargon stripped, the mechanism exposed, and a model they can reason with afterward.

## The rule that governs everything else

> Simplify the **language**. Never simplify the **mechanism**.

Say "the hammer counts blows per inch, and when the pile stops moving, that count *is* the
load test" — not "special equipment ensures the piles are strong enough." The first teaches
how it works. The second teaches nothing and sounds like marketing.

If making it simple would make it wrong, don't. Say the real thing and then unpack it.

## Structure

Adapt freely — this is the default shape, not a form to fill in.

1. **The problem.** What goes wrong without this thing? Start here, always. People
   understand solutions only after they feel the problem. One or two sentences.
2. **The idea.** The core move, in one sentence a stranger could repeat at dinner.
3. **The steps, in order.** How it actually plays out. Each step gets a plain-language
   heading and the real term alongside it. Explain *why* each step exists, not just that it
   happens — a step without a reason is trivia.
4. **The mental model.** One compressed line they'll still have next week. Bold it or set
   it off. This is the deliverable; everything above is scaffolding for it.
5. **The part people get wrong.** The common misconception, or the subtlety that separates
   someone who's read about it from someone who's done it. Often the most valuable section.
6. **Trade-offs**, when the thing is a *choice* among alternatives — why you'd pick it and
   when you wouldn't.

## Craft

- **Concrete beats abstract.** Real numbers, real objects, real consequences. "Cracks the
  drywall" lands; "may result in serviceability issues" does not.
- **Analogies are a loan, not a gift.** Use one, then say where it breaks down. An analogy
  left unqualified becomes the misconception you'll have to fix later.
- **Teach the vocabulary, don't hide it.** Give the plain words *and* the real term, so
  they can hold their own with a professional afterward. "Refusal — the point where the
  pile stops going down." Hiding the jargon leaves them unable to ask the next question.
- **Short paragraphs.** Two to four sentences. Prose over bullets for anything with cause
  and effect; bullets flatten reasoning into a list of unrelated facts.
- **Cut the throat-clearing.** No "great question", no "let's dive in", no summary of what
  you're about to say. Open on the problem.
- **Length follows the idea, not the format.** A simple thing gets four sentences. A system
  with five interacting parts gets a page. Padding a simple answer to look thorough is the
  same failure as compressing a complex one to look brisk.

## Match the audience

Ask only if it genuinely changes the answer; otherwise infer it and go.

| Audience | Optimize for |
|---|---|
| A curious adult (default) | The mental model and the why |
| A client or homeowner | What it costs them, what it protects, what decision they face |
| Crew or field staff | The sequence, what "done right" looks like, what fails if rushed |
| A lender, adjuster, or inspector | What's verifiable, what's documented, why it satisfies the requirement |
| A kid, genuinely | Analogy first, one idea only, no vocabulary homework |

If the user names a specific audience ("for a client", "so my dad gets it"), write it *to*
that person — not a general explanation with a note about them appended.

## Honesty

- Explaining simply is not license to invent. If a mechanism, number, or code requirement
  is uncertain, say which part you're unsure of rather than smoothing it into confident
  prose. Confident-and-wrong is the worst possible output of this skill.
- Where a detail depends on jurisdiction, engineering, or the specific product, say so and
  name who decides — the engineer of record, the AHJ, the manufacturer's listing.
- If the question rests on a false premise, fix the premise first. Explaining the mechanism
  of something that doesn't work that way is the most confusing possible answer.

## Anti-patterns

- Restating the jargon in slightly different jargon.
- A numbered list of steps with no causation — the reader can't reconstruct *why*.
- Burying the mental model in the last paragraph, or omitting it.
- Explaining the vocabulary and calling it an explanation. Words are not mechanism.
- Apologizing for complexity, or flattering the question. Just explain it.
- Ending with "let me know if you'd like me to go deeper" instead of judging the right
  depth and delivering it.

## Reference

`resources/worked-example.md` — a full explanation built on this structure (timber pile
foundations), annotated with which section is doing what and why. Read it when you want a
concrete sense of the target quality; skip it for short questions.
