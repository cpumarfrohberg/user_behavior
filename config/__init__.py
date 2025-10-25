import os
from enum import Enum

import ollama
from dotenv import load_dotenv

load_dotenv()


class ModelType(Enum):
    TINYLLAMA_1_1B = "tinyllama:1.1b"
    PHI3_MINI = "phi3:mini"
    LLAMA3_1_8B = "llama3.1:8b"
    MISTRAL_7B = "mistral:7b"


class SearchType(Enum):
    TEXT = "text"
    VECTOR_SENTENCE_TRANSFORMERS = "vector_sentence_transformers"


class SentenceTransformerModel(Enum):
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"


class APIEndpoint(Enum):
    """StackExchange API endpoints"""

    BASE_URL = "https://api.stackexchange.com/2.3"
    QUESTIONS = "questions"
    ANSWERS = "answers"
    SITES = "sites"


class StackExchangeSite(Enum):
    """Supported StackExchange sites for UX analysis"""

    USER_EXPERIENCE = "ux"


class DataType(Enum):
    """Types of data stored in MongoDB"""

    RAW_QUESTIONS = "raw_questions"
    RAW_ANSWERS = "raw_answers"
    PARSED_DOCUMENTS = "parsed_documents"
    RAG_INDEX = "rag_index"


DEFAULT_RAG_MODEL = ModelType.PHI3_MINI.value
DEFAULT_SEARCH_TYPE = SearchType.TEXT.value
DEFAULT_SENTENCE_TRANSFORMER_MODEL = SentenceTransformerModel.ALL_MINILM_L6_V2.value
DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 15
DEFAULT_CONTENT_FIELD = "content"
DEFAULT_MAX_CONTEXT_LENGTH = 1000

DEFAULT_NUM_RESULTS = 1

DEFAULT_SITE = StackExchangeSite.USER_EXPERIENCE.value
DEFAULT_BACKUP_SITE = StackExchangeSite.MONEY.value
DEFAULT_TAGS = [
    "usability",
    "user-interface",
    "user-experience",
    "interaction-design",
    "user-research",
    "user-testing",
    "user-feedback",
    "user-satisfaction",
]

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "ux_data")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_RAG_MODEL)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

ollama_client = ollama.Client(host=OLLAMA_HOST)
