from __future__ import annotations

from decimal import Decimal

from app.llm.cost import estimate_eur


def test_openai_mini_cost_is_positive() -> None:
    cost = estimate_eur("gpt-4.1-mini", prompt_tokens=10_000, completion_tokens=2_000)
    assert cost > Decimal("0")


def test_cached_tokens_are_cheaper_than_fresh() -> None:
    fresh = estimate_eur("claude-sonnet-4-6", prompt_tokens=10_000, completion_tokens=1_000)
    cached = estimate_eur(
        "claude-sonnet-4-6",
        prompt_tokens=10_000,
        completion_tokens=1_000,
        cached_tokens=9_000,
    )
    assert cached < fresh


def test_unknown_model_returns_zero() -> None:
    assert estimate_eur("imaginary-model", prompt_tokens=100, completion_tokens=100) == Decimal("0")
