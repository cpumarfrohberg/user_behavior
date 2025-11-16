"""Tools for Orchestrator Agent to call other agents"""

import logging
from typing import Any

from mongodb_agent.agent import MongoDBSearchAgent
from mongodb_agent.config import MongoDBConfig

logger = logging.getLogger(__name__)


PLACEHOLDER_CONFIDENCE = 0.0

# Global instances to avoid re-initialization
_mongodb_agent_instance: MongoDBSearchAgent | None = None
_mongodb_agent_config: MongoDBConfig | None = None


def initialize_mongodb_agent(config: MongoDBConfig | None = None) -> None:
    """Initialize MongoDB Agent instance for orchestrator to use"""
    global _mongodb_agent_instance, _mongodb_agent_config

    if config is None:
        config = MongoDBConfig()

    # Re-initialize if instance doesn't exist or if config changed significantly
    if _mongodb_agent_instance is None:
        logger.info("Initializing MongoDB Search Agent for orchestrator...")
        _mongodb_agent_instance = MongoDBSearchAgent(config)
        _mongodb_agent_instance.initialize()
        _mongodb_agent_config = config
        logger.info("MongoDB Search Agent initialized successfully")
    elif _mongodb_agent_config is not None and (
        _mongodb_agent_config.collection != config.collection
        or _mongodb_agent_config.openai_model != config.openai_model
    ):
        # Re-initialize if key config changed
        logger.info("Re-initializing MongoDB Search Agent due to config changes...")
        _mongodb_agent_instance = MongoDBSearchAgent(config)
        _mongodb_agent_instance.initialize()
        _mongodb_agent_config = config
        logger.info("MongoDB Search Agent re-initialized successfully")


async def call_mongodb_agent(question: str) -> dict[str, Any]:
    """
    Call MongoDB Agent to answer a question using document retrieval.

    Args:
        question: User question to answer

    Returns:
        Dictionary with answer, confidence, sources, and reasoning
    """
    global _mongodb_agent_instance

    if _mongodb_agent_instance is None:
        # Initialize with default config if not already initialized
        initialize_mongodb_agent()

    if _mongodb_agent_instance is None:
        raise RuntimeError("MongoDB Search Agent not initialized")

    logger.info(f"Calling MongoDB Search Agent with question: {question[:100]}...")

    try:
        result = await _mongodb_agent_instance.query(question)

        return {
            "answer": result.answer.answer,
            "confidence": result.answer.confidence,
            "sources_used": result.answer.sources_used,
            "reasoning": result.answer.reasoning,
            "tool_calls": len(result.tool_calls),
            "agent": "mongodb_agent",
        }
    except Exception as e:
        logger.error(f"Error calling MongoDB Search Agent: {e}")
        raise RuntimeError(f"MongoDB Search Agent failed: {str(e)}") from e


# Backward compatibility alias
async def call_rag_agent(question: str) -> dict[str, Any]:
    """Deprecated: Use call_mongodb_agent instead"""
    return await call_mongodb_agent(question)


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
        "confidence": PLACEHOLDER_CONFIDENCE,
        "reasoning": "Cypher Query Agent placeholder - not implemented",
        "agent": "cypher_query_agent",
    }
