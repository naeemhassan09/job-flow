from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from app.graph.workflow import build_workflow


def test_workflow_compiles_with_expected_nodes() -> None:
    graph = build_workflow(checkpointer=MemorySaver())
    node_names = set(graph.get_graph().nodes)
    expected = {"preprocess", "profile", "matcher", "generator", "evaluator"}
    assert expected <= node_names, f"missing nodes: {expected - node_names}"


def test_workflow_interrupts_before_evaluator() -> None:
    graph = build_workflow(checkpointer=MemorySaver())
    assert "evaluator" in (graph.interrupt_before_nodes or [])


def test_workflow_compiles_without_checkpointer() -> None:
    # Allowed for ad-hoc dry-runs; HITL pause won't persist but graph still builds.
    graph = build_workflow(checkpointer=None)
    assert graph is not None
