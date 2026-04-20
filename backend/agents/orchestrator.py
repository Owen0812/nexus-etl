import json
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import DocumentState
from backend.config import settings

_MAX_ATTEMPTS = 3


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.qwen_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0,
    )


def _get_strategy(llm: ChatOpenAI, filename: str) -> tuple[str, object]:
    """Call LLM to decide processing strategy; retry up to 3x with exponential backoff."""
    messages = [
        SystemMessage(content=(
            "You are a document routing agent. Based on the filename, decide if this PDF "
            "needs visual processing (scanned, has tables/images, complex layout) or can be "
            "handled as plain text.\n"
            'Return ONLY valid JSON: {"strategy": "vision"} or {"strategy": "text"}'
        )),
        HumanMessage(content=f"filename: {filename}"),
    ]

    last_response = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = llm.invoke(messages)
            last_response = resp
            strategy = json.loads(resp.content).get("strategy", "vision")
            if strategy in ("vision", "text"):
                return strategy, resp
        except Exception:
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)  # 1s → 2s

    # Default: vision is safer (handles all document types)
    return "vision", last_response


_EXTENSION_STRATEGY: dict[str, str] = {
    ".docx": "word",
    ".doc": "word",
    ".html": "html",
    ".htm": "html",
}


def orchestrator_node(state: DocumentState) -> dict:
    """Decide processing strategy based on file type.

    Word/HTML → deterministic from extension.
    PDF → LLM decides vision vs text.
    """
    suffix = state["filename"].rsplit(".", 1)[-1].lower()
    ext = f".{suffix}"

    if ext in _EXTENSION_STRATEGY:
        strategy = _EXTENSION_STRATEGY[ext]
        return {
            "processing_strategy": strategy,
            "current_stage": "orchestrated",
            "stages_completed": ["orchestrator"],
        }

    # PDF: ask LLM
    llm = _llm()
    strategy, response = _get_strategy(llm, state["filename"])

    result: dict = {
        "processing_strategy": strategy,
        "current_stage": "orchestrated",
        "stages_completed": ["orchestrator"],
    }
    if response is not None:
        result["messages"] = [response]
    return result


def route_after_orchestrator(state: DocumentState) -> str:
    if state.get("error"):
        return "error_handler"
    strategy = state.get("processing_strategy", "vision")
    return {
        "vision": "vision_extractor",
        "text": "text_extractor",
        "word": "word_extractor",
        "html": "html_extractor",
    }.get(strategy, "vision_extractor")
