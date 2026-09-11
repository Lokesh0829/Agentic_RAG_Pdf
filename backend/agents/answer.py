"""
agents/answer.py — LLM Answer Agent Node
Assembles final answer with citations and streaming support.
"""
import logging
from typing import AsyncIterator
from langchain_groq import ChatGroq

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from agents.state import AgentState
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = ChatGroq(
    model=settings.model,
    temperature=0.3,
)

_streaming_llm = ChatGroq(
    model=settings.model,
    temperature=0.3,
)

ANSWER_SYSTEM = """You are a helpful, expert document-based question answering assistant.

The documents may be written in Bengali.

Instructions:
1. Understand any Bengali content in the retrieved document context.
2. Answer the user's question in English. Do not respond in Bengali unless the user explicitly asks for Bengali.
3. Answer ONLY based on the provided context — do NOT use outside knowledge.
4. If the answer is not present in the context, say:
   "I could not find this information in the document."
5. Always cite the page number(s) where you found the information: [Page X] at the end of relevant sentences.
6. For tables, preserve the structure in your response using markdown.
7. If the question was about an image or chart, describe what the OCR text reveals.
"""


def _build_context(retrieved_docs: list[dict]) -> tuple[str, list[dict]]:
    """Build context string and citation list from retrieved docs."""
    context_parts = []
    citations = []

    seen_pages = set()
    for i, doc in enumerate(retrieved_docs):
        page = doc.get("page_num", 0)
        content_type = doc.get("content_type", "text")
        content = doc["content"]

        prefix = f"[Source {i+1}, Page {page}, Type: {content_type}]"
        context_parts.append(f"{prefix}\n{content}")

        if page and page not in seen_pages:
            seen_pages.add(page)
            citations.append({
                "page": page,
                "filename": doc.get("filename", ""),
                "content_type": content_type,
                "snippet": content[:150] + "...",
            })

    return "\n\n---\n\n".join(context_parts), citations


async def answer_node(state: AgentState) -> dict:
    """Prepare context and citations for answer streaming without double-invoking the LLM."""
    query = state["query"]
    retrieved_docs = state.get("retrieved_docs", [])

    logger.info(f"💬 AnswerAgent: preparing context and citations for '{query[:80]}'")

    context, citations = _build_context(retrieved_docs)

    steps = state.get("reasoning_steps", [])
    steps.append("Context and citations prepared for streaming answer")

    return {
        "answer": "",
        "citations": citations,
        "reasoning_steps": steps,
    }


async def answer_stream(state: AgentState) -> AsyncIterator[str]:
    """Stream the answer token by token (used by the SSE endpoint)."""
    query = state["query"]
    retrieved_docs = state.get("retrieved_docs", [])
    conversation_history = state.get("messages", [])

    context, _ = _build_context(retrieved_docs)

    history_text = ""
    recent_msgs = list(conversation_history)[-6:]
    for msg in recent_msgs:
        if isinstance(msg, HumanMessage):
            history_text += f"\nUser: {msg.content}"
        elif isinstance(msg, AIMessage):
            history_text += f"\nAssistant: {msg.content[:300]}..."

    user_prompt = f"""Previous conversation:{history_text if history_text else " (none)"}

Document Context:
{context}

Current Question: {query}

Answer with page citations:"""

    messages = [
        SystemMessage(content=ANSWER_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    async for chunk in _streaming_llm.astream(messages):
        if chunk.content:
            yield chunk.content
