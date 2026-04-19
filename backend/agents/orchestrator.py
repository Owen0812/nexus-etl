from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from backend.agents.state import DocumentState
from backend.config import settings


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.qwen_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0,
    )


def orchestrator_node(state: DocumentState) -> dict:
    """Inspect document characteristics and decide processing strategy."""
    llm = _llm()

    page_count = len(state.get("raw_pages", []))
    has_tables = bool(state.get("extracted_tables"))
    has_images = bool(state.get("extracted_images"))

    response = llm.invoke([
        SystemMessage(content=(
            "You are an ETL pipeline orchestrator. Analyse the document info and "
            "return a JSON array of stage names in execution order from: "
            "[vision_extractor, semantic_chunker, metadata_tagger, quality_agent]. "
            "Always include all four unless the document is empty."
        )),
        HumanMessage(content=(
            f"filename={state['filename']} pages={page_count} "
            f"has_tables={has_tables} has_images={has_images}"
        )),
    ])

    return {
        "current_stage": "orchestrated",
        "stages_completed": ["orchestrator"],
        "messages": [response],
    }


def route_after_orchestrator(state: DocumentState) -> str:
    if state.get("error"):
        return "error_handler"
    return "vision_extractor"


def build_orchestrator_subgraph():
    graph = StateGraph(DocumentState)
    graph.add_node("orchestrate", orchestrator_node)
    graph.set_entry_point("orchestrate")
    graph.add_edge("orchestrate", END)
    return graph.compile()
