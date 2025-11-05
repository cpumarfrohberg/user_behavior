"""Tools for Orchestrator Agent to call other agents"""

import logging
from typing import Any

from rag_agent.agent import RAGAgent
from rag_agent.config import RAGConfig
from rag_agent.models import RAGAnswer

logger = logging.getLogger(__name__)

# Global instances to avoid re-initialization
_rag_agent_instance: RAGAgent | None = None
_rag_agent_config: RAGConfig | None = None


def initialize_rag_agent(config: RAGConfig | None = None) -> None:
    """Initialize RAG Agent instance for orchestrator to use"""
    global _rag_agent_instance, _rag_agent_config

    if config is None:
        config = RAGConfig()

    # Re-initialize if instance doesn't exist or if config changed significantly
    if _rag_agent_instance is None:
        logger.info("Initializing RAG Agent for orchestrator...")
        _rag_agent_instance = RAGAgent(config)
        _rag_agent_instance.initialize()
        _rag_agent_config = config
        logger.info("RAG Agent initialized successfully")
    elif _rag_agent_config is not None and (
        _rag_agent_config.search_type != config.search_type
        or _rag_agent_config.collection != config.collection
        or _rag_agent_config.openai_model != config.openai_model
    ):
        # Re-initialize if key config changed
        logger.info("Re-initializing RAG Agent due to config changes...")
        _rag_agent_instance = RAGAgent(config)
        _rag_agent_instance.initialize()
        _rag_agent_config = config
        logger.info("RAG Agent re-initialized successfully")


async def call_rag_agent(question: str) -> dict[str, Any]:
    """
    Call RAG Agent to answer a question using document retrieval.

    Args:
        question: User question to answer

    Returns:
        Dictionary with answer, confidence, sources, and reasoning
    """
    global _rag_agent_instance

    if _rag_agent_instance is None:
        # Initialize with default config if not already initialized
        initialize_rag_agent()

    if _rag_agent_instance is None:
        raise RuntimeError("RAG Agent not initialized")

    logger.info(f"Calling RAG Agent with question: {question[:100]}...")

    try:
        answer, tool_calls = await _rag_agent_instance.query(question)

        return {
            "answer": answer.answer,
            "confidence": answer.confidence,
            "sources_used": answer.sources_used,
            "reasoning": answer.reasoning,
            "tool_calls": len(tool_calls),
            "agent": "rag_agent",
        }
    except Exception as e:
        logger.error(f"Error calling RAG Agent: {e}")
        raise RuntimeError(f"RAG Agent failed: {str(e)}") from e


async def call_cypher_query_agent(question: str) -> dict[str, Any]:
    """
    Call Cypher Query Agent to answer a question using graph queries.

    Args:
        question: User question to answer

    Returns:
        Dictionary with answer, confidence, and reasoning
    """
    # TODO: Implement Cypher Query Agent
    # For now, return a placeholder response
    logger.warning("Cypher Query Agent not yet implemented - returning placeholder")

    return {
        "answer": "Cypher Query Agent is not yet implemented. This would analyze graph relationships and patterns in Neo4j.",
        "confidence": 0.0,
        "reasoning": "Cypher Query Agent placeholder - not implemented",
        "agent": "cypher_query_agent",
    }
