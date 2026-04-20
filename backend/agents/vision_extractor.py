import base64
import io

import pdfplumber
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import DocumentState
from backend.config import settings


def _vision_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.qwen_vision_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0,
    )


def _page_image_b64(page) -> str:
    """Render a pdfplumber page to PNG and return base64 string."""
    img = page.to_image(resolution=150)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _analyze_table_image(b64: str, llm: ChatOpenAI) -> str:
    """Ask Qwen-VL to extract complex table structure."""
    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": "Extract and return the table data as JSON (list of row arrays)."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ])
    ])
    return response.content


def vision_extractor_node(state: DocumentState) -> dict:
    """Extract text, tables, and images from PDF; use Qwen-VL for complex tables."""
    llm = _vision_llm()
    pages, tables, images = [], [], []

    with pdfplumber.open(state["file_path"]) as pdf:
        for page_num, page in enumerate(pdf.pages):
            pages.append({
                "page_num": page_num,
                "text": page.extract_text() or "",
                "width": page.width,
                "height": page.height,
            })

            for tbl_idx, table_data in enumerate(page.extract_tables() or []):
                tables.append({
                    "page_num": page_num,
                    "table_index": tbl_idx,
                    "data": table_data,
                    "vision_description": None,  # populated below for complex tables
                })

            images.append({
                "page_num": page_num,
                "image_b64": _page_image_b64(page),
            })

    # Vision-enhance tables that have merged cells (heuristic: row count > 10)
    enhanced_tables = []
    for tbl in tables:
        if tbl["data"] and len(tbl["data"]) > 10:
            page_b64 = images[tbl["page_num"]]["image_b64"]
            tbl["vision_description"] = _analyze_table_image(page_b64, llm)
        enhanced_tables.append(tbl)

    return {
        "raw_pages": pages,
        "extracted_tables": enhanced_tables,
        "extracted_images": images,
        "stages_completed": ["vision_extractor"],
    }


def text_extractor_node(state: DocumentState) -> dict:
    """Fast path: pdfplumber text extraction only, no Qwen-VL calls."""
    pages, tables = [], []

    with pdfplumber.open(state["file_path"]) as pdf:
        for page_num, page in enumerate(pdf.pages):
            pages.append({
                "page_num": page_num,
                "text": page.extract_text() or "",
                "width": page.width,
                "height": page.height,
            })
            for tbl_idx, table_data in enumerate(page.extract_tables() or []):
                tables.append({
                    "page_num": page_num,
                    "table_index": tbl_idx,
                    "data": table_data,
                    "vision_description": None,
                })

    return {
        "raw_pages": pages,
        "extracted_tables": tables,
        "extracted_images": [],
        "stages_completed": ["vision_extractor"],  # same stage key for unified tracking
    }
