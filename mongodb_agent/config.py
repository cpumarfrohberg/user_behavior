# Configuration for MongoDB Agent
"""MongoDB Agent configuration dataclass"""

import os
from dataclasses import dataclass

from config import (
    MONGODB_DB,
    MONGODB_URI,
    OPENAI_RAG_MODEL,
    InstructionType,
)

# MongoDB Agent adaptive limit defaults
DEFAULT_INITIAL_MAX_TOOL_CALLS = int(os.getenv("DEFAULT_INITIAL_MAX_TOOL_CALLS", "3"))
DEFAULT_EXTENDED_MAX_TOOL_CALLS = int(os.getenv("DEFAULT_EXTENDED_MAX_TOOL_CALLS", "6"))
DEFAULT_ENABLE_ADAPTIVE_LIMIT = (
    os.getenv("DEFAULT_ENABLE_ADAPTIVE_LIMIT", "true").lower() == "true"
)


@dataclass
class MongoDBConfig:
    openai_model: str = OPENAI_RAG_MODEL
    instruction_type: InstructionType = InstructionType.MONGODB_AGENT
    initial_max_tool_calls: int = (
        DEFAULT_INITIAL_MAX_TOOL_CALLS  # Initial search limit before extension
    )
    extended_max_tool_calls: int = (
        DEFAULT_EXTENDED_MAX_TOOL_CALLS  # Maximum searches if extension is granted
    )
    enable_adaptive_limit: bool = DEFAULT_ENABLE_ADAPTIVE_LIMIT  # Enable adaptive limit extension based on search quality
    mongo_uri: str = MONGODB_URI
    database: str = MONGODB_DB
    collection: str = "questions"  # Updated to match actual collection name
