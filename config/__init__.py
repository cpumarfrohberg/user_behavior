import os
from enum import StrEnum

from dotenv import load_dotenv

from config.instructions import InstructionsConfig, InstructionType

load_dotenv(override=True)


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


class APIParameter(StrEnum):
    SORT_VOTES = "votes"
    SORT_CREATION = "creation"
    ORDER_DESC = "desc"
    ORDER_ASC = "asc"
    FILTER_WITHBODY = "withbody"


DEFAULT_PAGE = 1
DEFAULT_PAGESIZE = 50


class StackExchangeSite(StrEnum):
    USER_EXPERIENCE = "ux"


DEFAULT_RAG_MODEL = TokenizerModel.GPT_4O_MINI
DEFAULT_JUDGE_MODEL = (
    TokenizerModel.GPT_4O_MINI
)  # Using gpt-4o-mini for Judge (consistent validation, supports tools)

DEFAULT_TEMPERATURE = 0.3  # Lower temperature for more focused, deterministic responses
DEFAULT_RAG_TEMPERATURE = 0.3  # Temperature for RAG Agent (focused answers)
DEFAULT_JUDGE_TEMPERATURE = 0.1  # Lower temperature for Judge (consistent validation)
DEFAULT_MAX_TOKENS = (
    1000  # Increased for quantized models that need more tokens for JSON output
)
CYPHER_AGENT_MAX_TOKENS = (
    4000  # Higher limit for Cypher agent to handle large query results
)

DEFAULT_NUM_RESULTS = 1

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
DEFAULT_TOKENIZER_MODEL = TokenizerModel.GPT_4O_MINI
DEFAULT_TOKENIZER_ENCODING_FALLBACK = TokenizerEncoding.CL100K_BASE
DEFAULT_SCORE_ALPHA = 2.0
DEFAULT_SCORE_BETA = 0.5
DEFAULT_SCORE_GAMMA = 1.5
DEFAULT_TOKEN_NORMALIZATION_DIVISOR = 1000.0

DEFAULT_SITE = StackExchangeSite.USER_EXPERIENCE
DEFAULT_TAG = "user-behavior"
DEFAULT_PAGES = int(
    os.getenv("DEFAULT_PAGES", "5")
)  # Number of pages to fetch (50 questions per page)

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGO_DB_NAME", "stackexchange")
MONGODB_COLLECTION = os.getenv("MONGO_COLLECTION_NAME", "questions")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_RAG_MODEL = os.getenv("OPENAI_RAG_MODEL", str(DEFAULT_RAG_MODEL))
OPENAI_JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", str(DEFAULT_JUDGE_MODEL))


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/user_behavior_monitoring",
)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_secure_password")


ENABLE_ORCHESTRATOR_JUDGE = (
    os.getenv("ENABLE_ORCHESTRATOR_JUDGE", "false").lower() == "true"
)

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

BEHAVIOR_KEYWORDS = [
    "behavior",
    "satisfaction",
    "frustration",
    "user",
    "usability",
]
