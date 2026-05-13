---
name: eval-update
description: Use after modifying any prompt, node, router rule, or model selection in CareerOS AI. Reruns the affected eval slices, updates EVAL_REPORT.md, and pastes the comparison table into the PR. Invoke when the user says "the prompts changed", "I tuned the router", "switched a default model", or after merging anything under app/prompts/ or app/llm/.
---

# eval-update — refresh benchmarks after a behavior change

## When to run

- After any change under `app/prompts/`, `app/nodes/`, `app/llm/router.py`, or `app/llm/providers/`.
- After bumping a model version in the router config.
- Before opening a PR that could affect output quality.

## Workflow

1. Identify affected tasks. Mapping:
   - `prompts/extract.md` → JD parsing F1
   - `prompts/score.md` → fit MAE, decision accuracy
   - `prompts/generate.md` → factuality, ATS coverage
   - `prompts/research.md` → research relevance + groundedness
   - `prompts/evaluator.md` → quality-gate accuracy
   - Router/provider change → all of the above

2. Run only the affected runners:
   ```bash
   python -m evals.runners.run --task <task> --providers openai-mini,claude-haiku
   ```

3. Compare against `main`:
   ```bash
   python -m evals.runners.compare --base main --head HEAD
   ```

4. Regenerate the report:
   ```bash
   python -m evals.runners.report --output product-requirements/EVAL_REPORT.md
   ```

5. Paste the comparison table into the PR description.

## Block the PR if

- Any metric regresses > 5%.
- The dataset version changed without a corresponding ROADMAP entry.
- Real numbers aren't reproducible (someone hand-edited the report).

## Don't do this

- Don't write speculative numbers. If the eval didn't run, the row is `pending`.
- Don't skip the run "because the change is small." Prompts are sensitive — small wording shifts move metrics.
