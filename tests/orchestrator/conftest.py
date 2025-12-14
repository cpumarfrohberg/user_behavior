"""Test fixtures for Orchestrator Agent tests"""

import pytest
import pytest_asyncio

from mongodb_agent.config import MongoDBConfig
from orchestrator.agent import OrchestratorAgent
from orchestrator.config import OrchestratorConfig
from orchestrator.tools import mongodb_manager

# Test constants
TEST_TIMEOUT_SECONDS = 120
TEST_MIN_CONFIDENCE = 0.0
TEST_MAX_CONFIDENCE = 1.0
TEST_MIN_AGENTS_USED = 1
TEST_MIN_ANSWER_LENGTH = 0
TEST_MIN_REASONING_LENGTH = 0
TEST_MIN_TOKEN_COUNT = 0


@pytest.fixture
def mongodb_config():
    """MongoDBConfig for testing with real MongoDB"""
    config = MongoDBConfig()
    config.collection = "questions"  # Use the real collection
    return config


@pytest.fixture
def orchestrator_config():
    """OrchestratorConfig for testing"""
    config = OrchestratorConfig()
    config.enable_judge_evaluation = False  # Disable judge for faster tests
    return config


@pytest_asyncio.fixture
async def initialized_orchestrator(mongodb_config, orchestrator_config):
    """OrchestratorAgent initialized with real MongoDB data"""
    # Initialize MongoDB agent first (required by orchestrator)
    mongodb_manager.initialize(mongodb_config)

    # Initialize orchestrator
    orchestrator = OrchestratorAgent(orchestrator_config)
    orchestrator.initialize()
    return orchestrator
