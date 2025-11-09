# Configuration for RAG Agent
"""RAG Agent configuration dataclass"""

from dataclasses import dataclass

from config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_CONTEXT_LENGTH,
    MONGODB_DB,
    MONGODB_URI,
    OPENAI_RAG_MODEL,
    InstructionType,
    SearchType,
)


@dataclass
class RAGConfig:
    """Configuration for RAG system"""

    search_type: SearchType = SearchType.SENTENCE_TRANSFORMERS
    openai_model: str = OPENAI_RAG_MODEL  # OpenAI model name (e.g., "gpt-4o-mini")
    instruction_type: InstructionType = InstructionType.RAG_AGENT
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    max_context_length: int = DEFAULT_MAX_CONTEXT_LENGTH
    max_tool_calls: int = 5  # Maximum number of tool calls allowed (safety limit)
    mongo_uri: str = MONGODB_URI
    database: str = MONGODB_DB
    collection: str = "posts"
