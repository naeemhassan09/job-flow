from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.budget import BudgetExceeded, BudgetGuard


def _guard_with_spend(monthly: Decimal, workflow: Decimal) -> BudgetGuard:
    """Builds a BudgetGuard whose private spend lookups return canned values."""
    session = MagicMock()
    guard = BudgetGuard(
        session,
        monthly_cap_eur=Decimal("15.00"),
        per_workflow_cap_eur=Decimal("0.50"),
    )
    guard._spent_this_month = AsyncMock(return_value=monthly)  # type: ignore[method-assign]
    guard._spent_for_workflow = AsyncMock(return_value=workflow)  # type: ignore[method-assign]
    return guard


@pytest.mark.asyncio
async def test_precheck_passes_under_caps() -> None:
    guard = _guard_with_spend(monthly=Decimal("1.00"), workflow=Decimal("0.05"))
    await guard.precheck("wf-1")


@pytest.mark.asyncio
async def test_precheck_blocks_at_monthly_cap() -> None:
    guard = _guard_with_spend(monthly=Decimal("15.00"), workflow=Decimal("0.05"))
    with pytest.raises(BudgetExceeded) as exc:
        await guard.precheck("wf-1")
    assert exc.value.scope == "monthly"


@pytest.mark.asyncio
async def test_precheck_blocks_at_workflow_cap() -> None:
    guard = _guard_with_spend(monthly=Decimal("1.00"), workflow=Decimal("0.50"))
    with pytest.raises(BudgetExceeded) as exc:
        await guard.precheck("wf-1")
    assert exc.value.scope == "workflow"


@pytest.mark.asyncio
async def test_record_and_check_blocks_when_call_would_cross_monthly() -> None:
    guard = _guard_with_spend(monthly=Decimal("14.99"), workflow=Decimal("0.05"))
    with pytest.raises(BudgetExceeded) as exc:
        await guard.record_and_check("wf-1", Decimal("0.02"))
    assert exc.value.scope == "monthly"


@pytest.mark.asyncio
async def test_record_and_check_blocks_when_call_would_cross_workflow() -> None:
    guard = _guard_with_spend(monthly=Decimal("1.00"), workflow=Decimal("0.49"))
    with pytest.raises(BudgetExceeded) as exc:
        await guard.record_and_check("wf-1", Decimal("0.02"))
    assert exc.value.scope == "workflow"


@pytest.mark.asyncio
async def test_record_and_check_allows_within_caps() -> None:
    guard = _guard_with_spend(monthly=Decimal("1.00"), workflow=Decimal("0.10"))
    await guard.record_and_check("wf-1", Decimal("0.02"))
