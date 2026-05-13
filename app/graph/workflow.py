from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.state import JobSearchState
from app.nodes.evaluator import evaluator
from app.nodes.generator import generator
from app.nodes.matcher import matcher
from app.nodes.preprocess import preprocess
from app.nodes.profile import profile


def _after_preprocess(state: JobSearchState) -> Literal["profile", "__halt__"]:
    return "__halt__" if state.get("quarantined") else "profile"


def _after_matcher(state: JobSearchState) -> Literal["generator", "__skip__"]:
    """Spec §5.3 routing band: only the `apply` path runs the generator."""
    return "generator" if state.get("decision") == "apply" else "__skip__"


def build_workflow(checkpointer: BaseCheckpointSaver | None = None):
    """Assemble the LangGraph workflow.

    Interrupt-before-`evaluator` is wired so a human approval gate sits between
    the generator and the evaluator's final persistence step. The caller resumes
    with ``graph.invoke(None, config)`` after approval.
    """
    graph: StateGraph = StateGraph(JobSearchState)

    graph.add_node("preprocess", preprocess)
    graph.add_node("profile", profile)
    graph.add_node("matcher", matcher)
    graph.add_node("generator", generator)
    graph.add_node("evaluator", evaluator)

    graph.add_edge(START, "preprocess")
    graph.add_conditional_edges(
        "preprocess",
        _after_preprocess,
        {"profile": "profile", "__halt__": END},
    )
    graph.add_edge("profile", "matcher")
    graph.add_conditional_edges(
        "matcher",
        _after_matcher,
        {"generator": "generator", "__skip__": END},
    )
    graph.add_edge("generator", "evaluator")
    graph.add_edge("evaluator", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["evaluator"],
    )
