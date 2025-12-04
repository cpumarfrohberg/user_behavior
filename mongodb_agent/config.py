# Configuration for MongoDB Agent
"""MongoDB Agent configuration dataclass"""

from dataclasses import dataclass

from config import (
    MONGODB_DB,
    MONGODB_URI,
    OPENAI_RAG_MODEL,
    InstructionType,
)


@dataclass
class MongoDBConfig:
    """Configuration for MongoDB Agent system"""

    openai_model: str = OPENAI_RAG_MODEL  # OpenAI model name (e.g., "gpt-4o-mini")
    instruction_type: InstructionType = InstructionType.MONGODB_AGENT
    max_tool_calls: int = 7  # Maximum number of tool calls allowed (safety limit)
    mongo_uri: str = MONGODB_URI
    database: str = MONGODB_DB
    collection: str = "questions"  # Updated to match actual collection name
