"""Test fixtures for RAG Agent tests"""

import pytest
import pytest_asyncio

from config import SearchType
from rag_agent.agent import RAGAgent
from rag_agent.config import RAGConfig


@pytest.fixture
def agent_config():
    """RAGConfig for testing with real MongoDB and Ollama"""
    config = RAGConfig()
    config.collection = "questions"  # Use the real collection
    config.search_type = SearchType.MINSEARCH  # Use faster search for tests
    return config


@pytest_asyncio.fixture
async def initialized_agent(agent_config):
    """RAGAgent initialized with real MongoDB data"""
    agent = RAGAgent(agent_config)
    agent.initialize()
    return agent
