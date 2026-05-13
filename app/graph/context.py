from __future__ import annotations

from dataclasses import dataclass

from app.llm.router import Router
from app.profile import UserProfile


@dataclass(frozen=True)
class WorkflowContext:
    """Dependencies injected into every node call.

    Kept separate from JobSearchState because these are infrastructure (router,
    profile, db) rather than per-application data. LangGraph passes them via
    the ``config`` argument, not through the state dict.
    """

    router: Router
    profile: UserProfile
