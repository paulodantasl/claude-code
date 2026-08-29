# eli5

Explain anything in plain language without dumbing it down.

"ELI5" usually gets treated as a request for baby talk. It isn't — it's a request for
clarity. This skill simplifies the *language* while keeping the *mechanism* fully intact,
so the reader ends up able to reason about the thing rather than just nod at it.

## Install

```
/plugin marketplace add ./
/plugin install eli5
```

## Use

```
/eli5:eli5 how does a construction draw schedule actually work
/eli5:eli5 what a lien waiver does, for a homeowner
/eli5:eli5 explain vapor barriers to a new field super
```

Or just ask — the skill triggers on "explain", "in plain English", "break this down",
"I don't understand X", and requests for a version to hand a client, crew, or lender.

## What it produces

1. **The problem** — what goes wrong without this thing
2. **The idea** — the core move in one sentence
3. **The steps** — in order, each with the reason it exists
4. **The mental model** — one compressed line worth remembering
5. **The part people get wrong** — the misconception or the subtlety
6. **Trade-offs** — when the thing is a choice among alternatives

It adapts register to the audience (client, crew, lender, inspector, kid) and teaches the
real vocabulary alongside the plain words, so the reader can hold their own in the next
conversation with a professional.

## Contents

| Path | What it is |
|---|---|
| `skills/eli5/SKILL.md` | The skill — structure, craft rules, anti-patterns |
| `skills/eli5/resources/worked-example.md` | A full annotated explanation showing the target quality |
