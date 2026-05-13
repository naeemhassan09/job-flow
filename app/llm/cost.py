from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Approximate USD→EUR conversion. Update per quarter or pull from a daily FX cache later.
_USD_TO_EUR = Decimal("0.92")


@dataclass(frozen=True)
class ModelPricing:
    """USD per 1M tokens. Cached input pricing applies to Anthropic prompt cache hits."""

    prompt_usd_per_mtok: Decimal
    completion_usd_per_mtok: Decimal
    cached_usd_per_mtok: Decimal | None = None


# Pricing snapshot as of 2026-Q1. Treat as configuration, not source of truth — the
# eval harness reports real measured spend and reconciles drift.
PRICING: dict[str, ModelPricing] = {
    "gpt-4.1-mini": ModelPricing(Decimal("0.40"), Decimal("1.60")),
    "gpt-4.1": ModelPricing(Decimal("2.00"), Decimal("8.00")),
    "claude-haiku-4-5": ModelPricing(Decimal("1.00"), Decimal("5.00"), Decimal("0.10")),
    "claude-sonnet-4-6": ModelPricing(Decimal("3.00"), Decimal("15.00"), Decimal("0.30")),
}


def estimate_eur(
    model: str, *, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0
) -> Decimal:
    pricing = PRICING.get(model)
    if pricing is None:
        return Decimal("0")
    fresh_prompt = max(prompt_tokens - cached_tokens, 0)
    cached_rate = pricing.cached_usd_per_mtok or pricing.prompt_usd_per_mtok
    usd = (
        Decimal(fresh_prompt) * pricing.prompt_usd_per_mtok
        + Decimal(cached_tokens) * cached_rate
        + Decimal(completion_tokens) * pricing.completion_usd_per_mtok
    ) / Decimal(1_000_000)
    return (usd * _USD_TO_EUR).quantize(Decimal("0.000001"))
