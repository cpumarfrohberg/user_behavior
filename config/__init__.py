import os
from enum import StrEnum

import ollama
from dotenv import load_dotenv

# Import from instructions module (must be after StrEnum import)
from config.instructions import InstructionsConfig, InstructionType

load_dotenv(override=True)  # Override environment variables with .env values


class ModelType(StrEnum):
    PHI3_MINI = "phi3:mini"  # For Judge (strong reasoning, better for structured evaluation) - NOTE: Does not support tools
    LLAMA3_1_8B = "llama3.1:8b"  # Larger model (8B, needs more memory)
    LLAMA3_2_3B = "llama3.2:3b"  # For RAG Agent (faster generation, sufficient with good retrieval) - Supports tools
    LLAMA3_2_1B = "llama3.2:1b"  # Smallest model (1B, fastest) - Supports tools


class SearchType(StrEnum):
    MINSEARCH = "minsearch"
    SENTENCE_TRANSFORMERS = "sentence_transformers"


class SentenceTransformerModel(StrEnum):
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"


class TokenizerModel(StrEnum):
    """Tokenizer models for token counting"""

    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4O = "gpt-4o"


class TokenizerEncoding(StrEnum):
    """Tokenizer encoding fallbacks"""

    CL100K_BASE = "cl100k_base"
    P50K_BASE = "p50k_base"
    R50K_BASE = "r50k_base"


class APIEndpoint(StrEnum):
    """StackExchange API endpoints"""

    BASE_URL = "https://api.stackexchange.com/2.3"
    QUESTIONS = "questions"
    ANSWERS = "answers"
    SITES = "sites"
    USERS = "users"
    TAGS = "tags"
    COMMENTS = "comments"
    POSTS = "posts"
    SEARCH = "search"
    SIMILAR = "similar"


class StackExchangeSite(StrEnum):
    """Supported StackExchange sites for user behavior analysis"""

    USER_EXPERIENCE = "ux"


class DataType(StrEnum):
    """Types of data stored in MongoDB"""

    RAW_QUESTIONS = "raw_questions"
    RAW_ANSWERS = "raw_answers"
    PARSED_DOCUMENTS = "parsed_documents"
    RAG_INDEX = "rag_index"


DEFAULT_RAG_MODEL = ModelType.LLAMA3_2_3B  # Using llama3.2:3b for RAG (better quality, supports tools, sufficient with good retrieval)
DEFAULT_JUDGE_MODEL = (
    ModelType.PHI3_MINI
)  # Using phi3:mini for Judge (strong reasoning, better for structured evaluation)
DEFAULT_SEARCH_TYPE = SearchType.SENTENCE_TRANSFORMERS
DEFAULT_SENTENCE_TRANSFORMER_MODEL = SentenceTransformerModel.ALL_MINILM_L6_V2
DEFAULT_CHUNK_SIZE = (
    500  # Fewer chunks for speed (score: 1.157, tokens: 747.66, still perfect accuracy)
)
DEFAULT_CHUNK_OVERLAP = 0  # No overlap = faster chunking, fewer chunks
DEFAULT_CONTENT_FIELD = "content"
DEFAULT_MAX_CONTEXT_LENGTH = 800  # Reduced for speed (was 1000)

# LLM generation parameters
DEFAULT_TEMPERATURE = 0.3  # Lower temperature for more focused, deterministic responses
DEFAULT_RAG_TEMPERATURE = 0.3  # Temperature for RAG Agent (focused answers)
DEFAULT_JUDGE_TEMPERATURE = 0.1  # Lower temperature for Judge (consistent validation)
DEFAULT_MAX_TOKENS = (
    1000  # Increased for quantized models that need more tokens for JSON output
)

DEFAULT_NUM_RESULTS = 1

# Ground truth generation defaults
DEFAULT_GROUND_TRUTH_SAMPLES = int(os.getenv("DEFAULT_GROUND_TRUTH_SAMPLES", "50"))
DEFAULT_GROUND_TRUTH_OUTPUT = os.getenv(
    "DEFAULT_GROUND_TRUTH_OUTPUT", "evals/ground_truth.json"
)
DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH = int(
    os.getenv("DEFAULT_GROUND_TRUTH_MIN_TITLE_LENGTH", "10")
)
DEFAULT_GROUND_TRUTH_QUESTION_COLUMN = "question"
DEFAULT_GROUND_TRUTH_ID_COLUMN = "source"

# Evaluation defaults
DEFAULT_TOP_K = 5
DEFAULT_TOKENIZER_MODEL = TokenizerModel.GPT_4O_MINI
DEFAULT_TOKENIZER_ENCODING_FALLBACK = TokenizerEncoding.CL100K_BASE
DEFAULT_SCORE_ALPHA = 2.0
DEFAULT_SCORE_BETA = 0.5
DEFAULT_TOKEN_NORMALIZATION_DIVISOR = 1000.0
DEFAULT_GRID_SEARCH_SAMPLES = 10
DEFAULT_BEST_RESULTS_COUNT = 5
DEFAULT_SEARCH_TEXT_FIELDS = ["content", "title", "source"]
DEFAULT_CHUNK_TITLE = "Untitled"
DEFAULT_CHUNK_SOURCE = "Unknown"

# Grid search default ranges
DEFAULT_GRID_SEARCH_CHUNK_SIZES = [200, 300, 500, 1000]
DEFAULT_GRID_SEARCH_OVERLAPS = [0, 15, 50, 100]
DEFAULT_GRID_SEARCH_TOP_KS = [5, 10]
DEFAULT_GRID_SEARCH_RESULTS_OUTPUT = os.getenv(
    "DEFAULT_GRID_SEARCH_RESULTS_OUTPUT", "evals/results/grid_search_results.csv"
)

DEFAULT_SITE = StackExchangeSite.USER_EXPERIENCE
DEFAULT_TAG = "user-behavior"
DEFAULT_PAGES = int(
    os.getenv("DEFAULT_PAGES", "5")
)  # Number of pages to fetch (50 questions per page)

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGO_DB_NAME", "stackexchange")
MONGODB_COLLECTION = os.getenv("MONGO_COLLECTION_NAME", "questions")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_RAG_MODEL = os.getenv("OLLAMA_RAG_MODEL", DEFAULT_RAG_MODEL)
OLLAMA_JUDGE_MODEL = os.getenv("OLLAMA_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_secure_password")

# UX-related tags for relevance filtering
UX_TAGS = [
    "usability",
    "user-interface",
    "user-experience",
    "interaction-design",
    "user-research",
    "user-testing",
    "user-feedback",
    "user-satisfaction",
]

# Behavior keywords for relevance filtering
BEHAVIOR_KEYWORDS = [
    "behavior",
    "satisfaction",
    "frustration",
    "user",
    "usability",
]

# Ollama client (shared - model is specified per request)
ollama_client = ollama.Client(host=OLLAMA_HOST)
