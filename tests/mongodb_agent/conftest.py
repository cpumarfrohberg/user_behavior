"""Test fixtures for MongoDB Agent tests"""

import pytest
import pytest_asyncio

from mongodb_agent.agent import MongoDBSearchAgent
from mongodb_agent.config import MongoDBConfig


@pytest.fixture
def agent_config():
    """MongoDBConfig for testing with real MongoDB"""
    config = MongoDBConfig()
    config.collection = "questions"  # Use the real collection
    return config


@pytest_asyncio.fixture
async def initialized_agent(agent_config):
    """MongoDBSearchAgent initialized with real MongoDB data"""
    agent = MongoDBSearchAgent(agent_config)
    agent.initialize()
    return agent
