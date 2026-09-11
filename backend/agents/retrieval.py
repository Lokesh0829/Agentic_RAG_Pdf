"""
agents/retrieval.py — Retrieval Agent Node
Performs hybrid vector + keyword search and re-ranks results.
"""
import logging
from rank_bm25 import BM25Okapi

from agents.state import AgentState
from database import ChromaDB

logger = logging.getLogger(__name__)

TOP_K_VECTOR = 8
TOP_K_FINAL = 6


def _bm25_rerank(query: str, docs: list[dict]) -> list[dict]:
    """Re-rank documents using BM25 keyword scoring."""
    if not docs:
        return docs

    tokenized_corpus = [doc["content"].lower().split() for doc in docs]
    bm25 = BM25Okapi(tokenized_corpus)
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    for doc, score in zip(docs, scores):
        doc["bm25_score"] = float(score)

    # Combine vector + BM25 scores (normalize and add)
    max_bm25 = float(max(scores)) if max(scores) > 0 else 1.0
    for doc in docs:
        vector_score = float(doc.get("relevance_score", 0.5))
        bm25_normalized = float(doc["bm25_score"] / max_bm25)
        doc["combined_score"] = float(0.6 * vector_score + 0.4 * bm25_normalized)

    return sorted(docs, key=lambda x: x["combined_score"], reverse=True)


async def retrieval_node(state: AgentState) -> dict:
    """Retrieve relevant document chunks using hybrid search, structural layout, and targeted page mapping."""
    refined_query = state.get("refined_query") or state["query"]
    user_id = state["user_id"]
    doc_id = state["doc_id"]
    query_type = state.get("query_type", "factual")

    logger.info(f"🔎 RetrievalAgent: searching for '{refined_query[:80]}' in doc {doc_id}")

    try:
        vectorstore = ChromaDB.get_collection(user_id, doc_id)
        q_lower = refined_query.lower()

        # ─── 1. Targeted Page Retrieval ────────────────────────────────────────
        import re
        page_matches = re.findall(r"(?:page|p\.?)\s*(\d+)", q_lower)
        page_specific_docs = []
        if page_matches:
            target_pages = [int(p) for p in page_matches]
            logger.info(f"🎯 Target page query detected for pages: {target_pages}")
            try:
                for target_page in target_pages:
                    page_results = vectorstore.get(where={"page_num": target_page})
                    if page_results and "documents" in page_results:
                        for doc_text, metadata in zip(page_results["documents"], page_results["metadatas"]):
                            page_specific_docs.append({
                                "content": doc_text,
                                "metadata": metadata,
                                "relevance_score": 1.0,
                                "page_num": metadata.get("page_num", target_page),
                                "content_type": metadata.get("content_type", "text"),
                                "filename": metadata.get("filename", ""),
                            })
            except Exception as e:
                logger.warning(f"Error fetching target page docs: {e}")

        # ─── 2. Structural Document Retrieval (For global summaries/explains) ──
        is_global = any(kw in q_lower for kw in ["explain", "summarize", "summary", "about", "overview", "what is", "outline", "main topics", "key findings"])
        structural_docs = []
        if is_global:
            logger.info("ℹ️ Global summary query detected: fetching document structure (intro, abstract, conclusion)...")
            try:
                # Get first 3 pages (Title, Abstract, Introduction)
                first_pages = vectorstore.get(where={"page_num": {"$lte": 3}})
                if first_pages and "documents" in first_pages:
                    for doc_text, metadata in zip(first_pages["documents"], first_pages["metadatas"]):
                        structural_docs.append({
                            "content": doc_text,
                            "metadata": metadata,
                            "relevance_score": 1.0,
                            "page_num": metadata.get("page_num", 1),
                            "content_type": metadata.get("content_type", "text"),
                            "filename": metadata.get("filename", ""),
                        })
                
                # Get last 2 pages (Conclusion, Summary)
                from database import MongoDB
                from bson import ObjectId
                db = MongoDB.get_sync_db()
                doc_meta = db.documents.find_one({"_id": ObjectId(doc_id)})
                if doc_meta and "total_pages" in doc_meta:
                    total_pages = doc_meta["total_pages"]
                    if total_pages > 4:
                        last_pages = vectorstore.get(where={"page_num": {"$gte": total_pages - 1}})
                        if last_pages and "documents" in last_pages:
                            for doc_text, metadata in zip(last_pages["documents"], last_pages["metadatas"]):
                                structural_docs.append({
                                    "content": doc_text,
                                    "metadata": metadata,
                                    "relevance_score": 0.95,
                                    "page_num": metadata.get("page_num", total_pages),
                                    "content_type": metadata.get("content_type", "text"),
                                    "filename": metadata.get("filename", ""),
                                })
            except Exception as e:
                logger.warning(f"Error fetching structural pages for global query: {e}")

        # ─── 3. Standard Semantic Search ───────────────────────────────────────
        filter_dict = None
        if query_type == "table":
            filter_dict = {"content_type": "table"}
        elif query_type == "image":
            filter_dict = {"content_type": "image"}

        k_search = 15 if is_global else TOP_K_VECTOR
        if filter_dict:
            results = vectorstore.similarity_search_with_relevance_scores(
                refined_query, k=k_search, filter=filter_dict
            )
            if not results:
                results = vectorstore.similarity_search_with_relevance_scores(
                    refined_query, k=k_search
                )
        else:
            results = vectorstore.similarity_search_with_relevance_scores(
                refined_query, k=k_search
            )

        retrieved_docs = []
        for doc, score in results:
            retrieved_docs.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": float(score),
                "page_num": doc.metadata.get("page_num", 0),
                "content_type": doc.metadata.get("content_type", "text"),
                "filename": doc.metadata.get("filename", ""),
            })

        # Re-rank standard semantic search results
        retrieved_docs = _bm25_rerank(refined_query, retrieved_docs)
        retrieved_docs = retrieved_docs[:TOP_K_FINAL]

        # ─── 4. Combine and Remove Duplicates ──────────────────────────────────
        combined_list = page_specific_docs + structural_docs + retrieved_docs
        seen_signatures = set()
        final_docs = []
        for doc in combined_list:
            sig = (doc["page_num"], doc["content"].strip()[:120])
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                final_docs.append(doc)

        logger.info(f"✅ Combined retrieval yielded {len(final_docs)} unique chunks")

        steps = state.get("reasoning_steps", [])
        steps.append(f"Retrieved {len(final_docs)} chunks (targeted pages={len(page_specific_docs)}, structure={len(structural_docs)}, semantic={len(retrieved_docs)})")

        return {
            "retrieved_docs": final_docs,
            "reasoning_steps": steps,
        }

    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {
            "retrieved_docs": [],
            "reasoning_steps": state.get("reasoning_steps", []) + [f"Retrieval error: {e}"],
        }
