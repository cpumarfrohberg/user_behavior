"""Tools for Orchestrator Agent to call other agents"""

import asyncio
import logging
from typing import Any

from mongodb_agent.agent import MongoDBSearchAgent
from mongodb_agent.config import MongoDBConfig

logger = logging.getLogger(__name__)


PLACEHOLDER_CONFIDENCE = 0.0
ERROR_CONFIDENCE = 0.0
MIN_CONFIDENCE = 0.0
NUM_AGENTS_FOR_AVERAGING = 2  # Number of agents to average confidence from
DEFAULT_TOOL_CALLS = 0  # Default value for tool_calls when not present
QUESTION_LOG_TRUNCATE_LENGTH = 100  # Maximum length for question in log messages

# Global instances to avoid re-initialization
_mongodb_agent_instance: MongoDBSearchAgent | None = None
_mongodb_agent_config: MongoDBConfig | None = None


def _should_reinitialize_agent(
    current_config: MongoDBConfig | None, new_config: MongoDBConfig
) -> bool:
    if current_config is None:
        return False
    return current_config != new_config


def _create_mongodb_agent(config: MongoDBConfig) -> MongoDBSearchAgent:
    agent = MongoDBSearchAgent(config)
    agent.initialize()
    return agent


def initialize_mongodb_agent(config: MongoDBConfig | None = None) -> None:
    """Initialize MongoDB Agent instance for orchestrator to use"""
    global _mongodb_agent_instance, _mongodb_agent_config

    if config is None:
        config = MongoDBConfig()

    if _mongodb_agent_instance is None:
        logger.info("Initializing MongoDB Search Agent for orchestrator...")
        _mongodb_agent_instance = _create_mongodb_agent(config)
        _mongodb_agent_config = config
        logger.info("MongoDB Search Agent initialized successfully")
    elif _should_reinitialize_agent(_mongodb_agent_config, config):
        logger.info("Re-initializing MongoDB Search Agent due to config changes...")
        _mongodb_agent_instance = _create_mongodb_agent(config)
        _mongodb_agent_config = config
        logger.info("MongoDB Search Agent re-initialized successfully")


def _ensure_mongodb_agent_initialized() -> None:
    """Ensure MongoDB agent is initialized, creating it if needed."""
    global _mongodb_agent_instance
    if _mongodb_agent_instance is None:
        initialize_mongodb_agent()
    if _mongodb_agent_instance is None:
        raise RuntimeError("MongoDB Search Agent not initialized")


def _format_mongodb_result(result: Any) -> dict[str, Any]:
    return {
        "answer": result.answer.answer,
        "confidence": result.answer.confidence,
        "sources_used": result.answer.sources_used,
        "reasoning": result.answer.reasoning,
        "tool_calls": len(result.tool_calls),
        "agent": "mongodb_agent",
    }


async def call_mongodb_agent(question: str) -> dict[str, Any]:
    global _mongodb_agent_instance

    _ensure_mongodb_agent_initialized()

    logger.info(
        f"Calling MongoDB Search Agent with question: {question[:QUESTION_LOG_TRUNCATE_LENGTH]}..."
    )

    try:
        result = await _mongodb_agent_instance.query(question)
        return _format_mongodb_result(result)
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


def _handle_agent_error(error: Exception, agent_name: str) -> dict[str, Any]:
    """
    Convert agent exception to error result dict.

    Args:
        error: The exception that occurred
        agent_name: Name of the agent that failed

    Returns:
        Error result dictionary
    """
    logger.error(f"{agent_name} failed: {error}")
    return {
        "answer": f"{agent_name} encountered an error.",
        "confidence": ERROR_CONFIDENCE,
        "sources_used": [],
        "reasoning": f"Error: {str(error)}",
        "agent": agent_name,
    }


def _calculate_combined_confidence(
    mongodb_result: dict[str, Any], cypher_result: dict[str, Any]
) -> float:
    """
    Calculate combined confidence from both agent results.

    Args:
        mongodb_result: MongoDB agent result dict
        cypher_result: Cypher agent result dict

    Returns:
        Combined confidence value (0.0 to 1.0)
    """
    mongodb_conf = mongodb_result.get("confidence", MIN_CONFIDENCE)
    cypher_conf = cypher_result.get("confidence", MIN_CONFIDENCE)

    # If one is placeholder, use the other
    if cypher_conf == PLACEHOLDER_CONFIDENCE:
        return mongodb_conf
    if mongodb_conf == MIN_CONFIDENCE:
        return cypher_conf

    # Average both confidences
    return (mongodb_conf + cypher_conf) / float(NUM_AGENTS_FOR_AVERAGING)


def _format_combined_answer(
    mongodb_result: dict[str, Any], cypher_result: dict[str, Any]
) -> str:
    mongodb_answer = mongodb_result.get("answer", "")
    cypher_answer = cypher_result.get("answer", "")
    return f"{mongodb_answer}\n\nGraph Analysis: {cypher_answer}".strip()


def _format_combined_reasoning(
    mongodb_result: dict[str, Any], cypher_result: dict[str, Any]
) -> str:
    mongodb_reasoning = mongodb_result.get("reasoning", "")
    cypher_reasoning = cypher_result.get("reasoning", "")
    return f"MongoDB Agent: {mongodb_reasoning}\nCypher Query Agent: {cypher_reasoning}"


def _combine_agent_results(
    mongodb_result: dict[str, Any], cypher_result: dict[str, Any]
) -> dict[str, Any]:
    """
    Combine results from MongoDB and Cypher agents into single response.

    Args:
        mongodb_result: MongoDB agent result dict
        cypher_result: Cypher agent result dict

    Returns:
        Combined result dictionary
    """
    combined_confidence = _calculate_combined_confidence(mongodb_result, cypher_result)
    combined_answer = _format_combined_answer(mongodb_result, cypher_result)
    combined_reasoning = _format_combined_reasoning(mongodb_result, cypher_result)

    return {
        "answer": combined_answer,
        "confidence": combined_confidence,
        "sources_used": mongodb_result.get("sources_used", []),
        "reasoning": combined_reasoning,
        "agents_used": ["mongodb_agent", "cypher_query_agent"],
        "tool_calls": mongodb_result.get("tool_calls", DEFAULT_TOOL_CALLS),
    }


async def _run_agents_parallel(question: str) -> dict[str, dict[str, Any]]:
    """
    Run both agents in parallel and return their results.

    Args:
        question: User question to answer

    Returns:
        Dictionary with keys 'mongodb' and 'cypher' containing result dictionaries
    """
    # Define agents to run with their display names
    agent_configs = {
        "mongodb": ("MongoDB agent", call_mongodb_agent),
        "cypher": ("Cypher agent", call_cypher_query_agent),
    }

    # Create tasks for all agents
    tasks = {
        key: asyncio.create_task(agent_func(question))
        for key, (_, agent_func) in agent_configs.items()
    }

    # Gather all results
    results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)

    # Map results back to named keys and handle errors
    results = {}
    for (key, (agent_name, _)), result in zip(agent_configs.items(), results_list):
        if isinstance(result, Exception):
            result = _handle_agent_error(result, agent_name)
        results[key] = result

    return results


async def call_both_agents_parallel(question: str) -> dict[str, Any]:
    """
    Call both MongoDB and Cypher Query agents in parallel for comprehensive analysis.

    This tool runs both agents concurrently, which is faster than calling them sequentially.
    Use this when a question requires both document retrieval AND relationship analysis.

    Args:
        question: User question to answer

    Returns:
        Dictionary with combined answer, confidence, sources, and reasoning from both agents
    """
    logger.info(
        f"Calling both agents in parallel for question: {question[:QUESTION_LOG_TRUNCATE_LENGTH]}..."
    )

    try:
        results = await _run_agents_parallel(question)
        return _combine_agent_results(results["mongodb"], results["cypher"])
    except Exception as e:
        logger.error(f"Error in parallel agent execution: {e}")
        raise RuntimeError(f"Parallel agent execution failed: {str(e)}") from e
