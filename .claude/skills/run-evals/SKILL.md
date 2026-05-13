---
name: run-evals
description: Use when the user asks to run the CareerOS eval harness, compare OpenAI vs Claude on the labeled JD/CV dataset, regenerate the benchmark numbers in EVAL_REPORT.md, or check if a PR regresses metrics. Triggers on "run evals", "compare providers", "update benchmark", "regression check".
---

# run-evals — execute the CareerOS eval harness

## What runs

`evals/` contains:
- `dataset/` — 50 labeled JD/CV pairs (25 real, 25 synthetic edge cases)
- `runners/` — one runner per metric (parsing F1, fit MAE, decision accuracy, factuality, ATS coverage, research groundedness)
- `reports/` — generated benchmark output

## Standard command

```bash
docker compose up -d postgres
uv sync
pytest evals/ -v
python -m evals.runners.report --providers openai-mini,claude-haiku --output product-requirements/EVAL_REPORT.md
```

## Comparing providers

The runner always evaluates both `gpt-4.1-mini` and `claude-haiku-4-5` in parallel using `asyncio.gather`. It emits a markdown table in PR-friendly format. Paste this into the PR comment when you regenerate.

## Regression policy

- Fail PR if any metric drops > 5% vs. `main`.
- Manual override requires reviewer note in the PR description.
- `.github/workflows/eval.yml` enforces this on every PR touching `app/prompts/`, `app/nodes/`, `app/llm/`, or `evals/`.

## Adding a new metric

1. Add a runner in `evals/runners/<metric>.py` that returns a `MetricResult`.
2. Add a labeled column to `dataset/labels.jsonl`.
3. Add a row to the `metrics` registry in `evals/runners/__init__.py`.
4. Update [EVAL_REPORT.md](../../product-requirements/EVAL_REPORT.md) header.

## Cost note

Evals call real LLMs. Use `--sample 5` for fast smoke-checks during development. Full 50-pair run is gated to PRs and the nightly job to avoid burning the daily budget.
