from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.state import DocumentState
from backend.agents.increment_checker import increment_checker_node
from backend.agents.orchestrator import orchestrator_node, route_after_orchestrator
from backend.agents.vision_extractor import vision_extractor_node
from backend.agents.semantic_chunker import semantic_chunker_node
from backend.agents.metadata_tagger import metadata_tagger_node
from backend.agents.quality_agent import quality_agent_node


def _error_handler(state: DocumentState) -> dict:
    return {"current_stage": "error"}


def build_pipeline_graph():
    """Assemble the full LangGraph ETL pipeline."""
    g = StateGraph(DocumentState)

    g.add_node("increment_checker", increment_checker_node)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("vision_extractor", vision_extractor_node)
    g.add_node("semantic_chunker", semantic_chunker_node)
    g.add_node("metadata_tagger", metadata_tagger_node)
    g.add_node("quality_agent", quality_agent_node)
    g.add_node("error_handler", _error_handler)

    g.set_entry_point("increment_checker")

    # Skip entire pipeline for duplicates
    g.add_conditional_edges(
        "increment_checker",
        lambda s: END if s.get("is_duplicate") else "orchestrator",
    )
    g.add_conditional_edges("orchestrator", route_after_orchestrator)

    g.add_edge("vision_extractor", "semantic_chunker")
    g.add_edge("semantic_chunker", "metadata_tagger")
    g.add_edge("metadata_tagger", "quality_agent")
    g.add_edge("quality_agent", END)
    g.add_edge("error_handler", END)

    return g.compile(checkpointer=MemorySaver())


# Module-level singleton — imported by Celery task
pipeline_graph = build_pipeline_graph()
