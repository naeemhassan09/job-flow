---
name: scope-check
description: Use BEFORE adding any new feature, node, agent, dashboard, retrieval system, or LLM call to CareerOS AI. Validates the change against spec Section 3 (IN/OUT) and Section 22 (anti-patterns). Invoke when the user requests something like "add a reflection loop", "add embeddings", "add another agent", "add a Streamlit page", "add scraping", "auto-apply", or anything that sounds like scope creep.
---

# scope-check — CareerOS AI scope guardrail

Before writing the change, walk this checklist explicitly. Cite the relevant spec section in your response.

## The IN/OUT checklist (spec Section 3)

Ask:

1. **Is this on the IN list (Section 3.1)?** If yes, proceed.
2. **Is this on the OUT list (Section 3.2)?** If yes, push back. Quote the row's reason verbatim.
3. **Is this on the explicit-non-goals list (Section 3.3)?** If yes, refuse. These are non-negotiable safety/ethics lines.
4. **Is it a stretch item (Section 21)?** Only proceed if V1 is genuinely complete — check ROADMAP.md status before agreeing.

## Scope expansion log (post-spec)

The spec Section 3.2 ban on scraping has been refined per user direction 2026-05-14:

- **Adzuna API**, **Reed API**: IN (official partner APIs, not scraping).
- **LinkedIn / Indeed direct scraping**: STILL OUT. These remain extension-only (week 5). Never write code that hits LI/Indeed HTML endpoints.

If asked to add a new source: default-reject anything requiring bypass of paywall/auth-wall/robots.txt; surface the trade-off before writing code.

## The anti-patterns checklist (spec Section 22)

Refuse or refactor if the request matches any of:

1. Calling a CRUD service an "agent"
2. Adding embeddings without something to retrieve over
3. Adding a reflection loop (N=1 user)
4. Shipping a Streamlit dashboard alongside Next.js
5. Claiming "production" with SQLite
6. Writing aspirational metrics anywhere
7. Burying platform positioning under the job-search use case

## The dual-goal test (spec Section 2)

A feature must serve **both** goals:
- **Portfolio**: does a senior reviewer pattern-match it to enterprise platform engineering?
- **Personal use**: will the author actually use it during his job search?

If only one — cut.

## Response template

When you trigger this skill, write:

```
## Scope check

Requested: <one line>

Spec status: <IN sectionX.Y | OUT Section 3.2 row "<...>" | non-goal Section 3.3 | stretch Section 21 | not in spec>

Anti-pattern flags: <none | list>

Dual-goal: <both | portfolio only | personal only>

Recommendation: <proceed | refactor to <...> | decline because <quoted reason>>
```

Then act on the recommendation. Do not silently proceed past a flag.
