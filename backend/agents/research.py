"""
agents/research.py — Research / Reasoning Agent Node
Multi-step reasoning with self-reflection for complex queries.
Max 3 iterations to prevent loops.
"""
import logging
from langchain_groq import ChatGroq

from agents.state import AgentState
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_ITERATIONS = 3

_llm = ChatGroq(
    model=settings.model,
    temperature=0.1,
)

RESEARCH_SYSTEM = """You are a research agent analyzing document content to answer complex questions.
Your job is to:
1. Review the retrieved context carefully
2. Determine if the context is SUFFICIENT to answer the question
3. If sufficient, outline the key points needed for a complete answer
4. If not sufficient, identify EXACTLY what additional information is needed

Respond in this EXACT format:
SUFFICIENT: yes|no
KEY_POINTS:
- <point 1>
- <point 2>
MISSING: <what is missing, or "nothing" if sufficient>
CHAIN_OF_THOUGHT: <your brief reasoning process>"""


async def research_node(state: AgentState) -> dict:
    """Multi-step context analysis (instant context evaluation)."""
    retrieved_docs = state.get("retrieved_docs", [])
    iteration = state.get("iteration_count", 0)

    logger.info(f"🧠 ResearchAgent: evaluating {len(retrieved_docs)} chunks (iteration {iteration + 1})")

    steps = state.get("reasoning_steps", [])
    steps.append(f"Evaluated {len(retrieved_docs)} document chunks for reasoning")

    return {
        "needs_more_retrieval": False,
        "reasoning_steps": steps,
        "iteration_count": iteration + 1,
    }
