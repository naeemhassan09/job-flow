from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

registry = CollectorRegistry()

workflow_started = Counter(
    "careeros_workflow_started_total", "Workflows started", ["source"], registry=registry
)
workflow_completed = Counter(
    "careeros_workflow_completed_total",
    "Workflows completed",
    ["status"],
    registry=registry,
)
llm_call_cost_eur = Histogram(
    "careeros_llm_call_cost_eur",
    "Per-call estimated cost in EUR",
    ["provider", "model"],
    registry=registry,
    buckets=(0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
)


router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
