---
name: scope-check
description: Use BEFORE adding any new feature, node, agent, dashboard, retrieval system, or LLM call to CareerOS AI. Validates the change against spec §3 (IN/OUT) and §22 (anti-patterns). Invoke when the user requests something like "add a reflection loop", "add embeddings", "add another agent", "add a Streamlit page", "add scraping", "auto-apply", or anything that sounds like scope creep.
---

# scope-check — CareerOS AI scope guardrail

Before writing the change, walk this checklist explicitly. Cite the relevant spec section in your response.

## The IN/OUT checklist (spec §3)

Ask:

1. **Is this on the IN list (§3.1)?** If yes, proceed.
2. **Is this on the OUT list (§3.2)?** If yes, push back. Quote the row's reason verbatim.
3. **Is this on the explicit-non-goals list (§3.3)?** If yes, refuse. These are non-negotiable safety/ethics lines.
4. **Is it a stretch item (§21)?** Only proceed if V1 is genuinely complete — check ROADMAP.md status before agreeing.

## The anti-patterns checklist (spec §22)

Refuse or refactor if the request matches any of:

1. Calling a CRUD service an "agent"
2. Adding embeddings without something to retrieve over
3. Adding a reflection loop (N=1 user)
4. Shipping a Streamlit dashboard alongside Next.js
5. Claiming "production" with SQLite
6. Writing aspirational metrics anywhere
7. Burying platform positioning under the job-search use case

## The dual-goal test (spec §2)

A feature must serve **both** goals:
- **Portfolio**: does a senior reviewer pattern-match it to enterprise platform engineering?
- **Personal use**: will the author actually use it during his job search?

If only one — cut.

## Response template

When you trigger this skill, write:

```
## Scope check

Requested: <one line>

Spec status: <IN §X.Y | OUT §3.2 row "<...>" | non-goal §3.3 | stretch §21 | not in spec>

Anti-pattern flags: <none | list>

Dual-goal: <both | portfolio only | personal only>

Recommendation: <proceed | refactor to <...> | decline because <quoted reason>>
```

Then act on the recommendation. Do not silently proceed past a flag.
