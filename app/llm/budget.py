from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMUsageEvent


class BudgetExceeded(Exception):
    """Raised when a planned LLM call would exceed a budget cap."""

    def __init__(self, scope: str, spent: Decimal, cap: Decimal) -> None:
        super().__init__(f"{scope} budget exceeded: spent={spent} cap={cap}")
        self.scope = scope
        self.spent = spent
        self.cap = cap


class BudgetGuard:
    """Hard monthly cap + per-workflow soft cap.

    Consulted before every LLM call. ``check_and_record`` is intended to be called
    after a successful provider response — it records the actual spend and raises
    if the running total has now crossed a cap. ``precheck`` is the optional
    pre-call gate that uses the running total alone.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        monthly_cap_eur: Decimal,
        per_workflow_cap_eur: Decimal,
    ) -> None:
        self._session = session
        self._monthly_cap = monthly_cap_eur
        self._workflow_cap = per_workflow_cap_eur

    async def precheck(self, workflow_id: str) -> None:
        monthly = await self._spent_this_month()
        if monthly >= self._monthly_cap:
            raise BudgetExceeded("monthly", monthly, self._monthly_cap)
        workflow = await self._spent_for_workflow(workflow_id)
        if workflow >= self._workflow_cap:
            raise BudgetExceeded("workflow", workflow, self._workflow_cap)

    async def record_and_check(self, workflow_id: str, cost_eur: Decimal) -> None:
        monthly = await self._spent_this_month()
        workflow = await self._spent_for_workflow(workflow_id)
        if monthly + cost_eur > self._monthly_cap:
            raise BudgetExceeded("monthly", monthly + cost_eur, self._monthly_cap)
        if workflow + cost_eur > self._workflow_cap:
            raise BudgetExceeded("workflow", workflow + cost_eur, self._workflow_cap)

    async def _spent_this_month(self) -> Decimal:
        now = datetime.now(tz=UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.coalesce(func.sum(LLMUsageEvent.estimated_cost_eur), 0)).where(
            LLMUsageEvent.created_at >= start
        )
        result = await self._session.execute(stmt)
        return Decimal(result.scalar_one())

    async def _spent_for_workflow(self, workflow_id: str) -> Decimal:
        stmt = select(func.coalesce(func.sum(LLMUsageEvent.estimated_cost_eur), 0)).where(
            LLMUsageEvent.workflow_id == workflow_id
        )
        result = await self._session.execute(stmt)
        return Decimal(result.scalar_one())
