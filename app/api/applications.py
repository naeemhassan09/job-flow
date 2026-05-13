from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.graph.checkpointer import get_checkpointer
from app.graph.runtime import get_context, runnable_config
from app.graph.state import JobSearchState
from app.graph.workflow import build_workflow

router = APIRouter(prefix="/api/applications", tags=["applications"])

Source = Literal["paste", "linkedin", "indeed"]


class CreateApplicationRequest(BaseModel):
    raw_jd: str = Field(min_length=1)
    source: Source = "paste"
    url: str | None = None
    captured_at: datetime | None = None


class CreateApplicationResponse(BaseModel):
    application_id: str
    workflow_id: str
    status: str


class ApprovalRequest(BaseModel):
    note: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateApplicationResponse)
async def create_application(req: CreateApplicationRequest) -> CreateApplicationResponse:
    """Create a new application record and start the workflow. The workflow
    runs synchronously up to the HITL interrupt (before `evaluator`) and pauses.
    """
    application_id = str(uuid.uuid4())
    workflow_id = application_id  # 1:1 in V1
    initial: JobSearchState = {
        "application_id": application_id,
        "workflow_id": workflow_id,
        "raw_jd": req.raw_jd,
        "current_step": "queued",
    }
    async with get_checkpointer() as cp:
        graph = build_workflow(checkpointer=cp)
        await graph.ainvoke(initial, runnable_config(workflow_id, context=get_context()))
    return CreateApplicationResponse(
        application_id=application_id, workflow_id=workflow_id, status="awaiting_approval"
    )


@router.post("/{application_id}/approve")
async def approve(application_id: str, _: ApprovalRequest = ApprovalRequest()) -> dict[str, str]:
    """Resume the workflow past the HITL interrupt → runs evaluator + final persistence."""
    async with get_checkpointer() as cp:
        graph = build_workflow(checkpointer=cp)
        cfg = runnable_config(application_id, context=get_context())
        snapshot = await graph.aget_state(cfg)
        if not snapshot or not snapshot.next:
            raise HTTPException(status_code=409, detail="workflow is not paused at HITL gate")
        await graph.ainvoke(None, cfg)
    return {"application_id": application_id, "status": "approved", "approved_at": _utc_iso()}


@router.post("/{application_id}/reject")
async def reject(application_id: str, _: ApprovalRequest = ApprovalRequest()) -> dict[str, str]:
    """Cancel the workflow at the HITL gate; the draft is not persisted."""
    async with get_checkpointer() as cp:
        graph = build_workflow(checkpointer=cp)
        cfg = runnable_config(application_id, context=get_context())
        snapshot = await graph.aget_state(cfg)
        if not snapshot or not snapshot.next:
            raise HTTPException(status_code=409, detail="workflow is not paused at HITL gate")
        await graph.aupdate_state(cfg, {"awaiting_approval": False, "current_step": "rejected"})
    return {"application_id": application_id, "status": "rejected", "rejected_at": _utc_iso()}


@router.get("/{application_id}")
async def get_application(application_id: str) -> dict[str, object]:
    async with get_checkpointer() as cp:
        graph = build_workflow(checkpointer=cp)
        snapshot = await graph.aget_state(runnable_config(application_id, context=get_context()))
        if not snapshot:
            raise HTTPException(status_code=404, detail="application not found")
        return {
            "application_id": application_id,
            "values": snapshot.values,
            "next_nodes": list(snapshot.next or []),
        }


def _utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
