import os
from enum import Enum
from typing import Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class InstructionType(Enum):
    FAQ_ASSISTANT = "faq_assistant"
    TECHNICAL_SUPPORT = "technical_support"


class PromptTemplate(Enum):
    FAQ_ASSISTANT = """
<QUESTION>
{question}
</QUESTION>

<CONTEXT>
{context}
</CONTEXT>
""".strip()

    TECHNICAL_SUPPORT = """
<QUESTION>
{question}
</QUESTION>

<TECHNICAL_CONTEXT>
{context}
</TECHNICAL_CONTEXT>

Please provide a clear, step-by-step solution based on the technical context above.
""".strip()


class InstructionsConfig:
    INSTRUCTIONS: Dict[InstructionType, str] = {
        InstructionType.FAQ_ASSISTANT: """
You're a helpful FAQ assistant. Answer questions based on the provided CONTEXT.
Be concise, accurate, and helpful. If you don't know the answer based on the context, say so.
""".strip(),
        InstructionType.TECHNICAL_SUPPORT: """
You're a technical support assistant. Help users with technical questions.
Provide clear, step-by-step solutions when possible.
Use the CONTEXT to provide accurate technical information.
""".strip(),
    }


class ModelType(Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_3_5_TURBO = "gpt-3.5-turbo"


class ChunkingConfig(Enum):
    DEFAULT_SIZE = 2000
    DEFAULT_OVERLAP = 0.5
    DEFAULT_CONTENT_FIELD = "content"


class RepositoryConfig(Enum):
    DEFAULT_OWNER = "pydantic"
    DEFAULT_NAME = "pydantic-ai"
    DEFAULT_EXTENSIONS = {"md", "mdx"}
    GITHUB_CODELOAD_URL = "https://codeload.github.com"


class SearchType(Enum):
    TEXT = "text"
    VECTOR_MINSEARCH = "vector_minsearch"
    VECTOR_SENTENCE_TRANSFORMERS = "vector_sentence_transformers"


class SentenceTransformerModel(Enum):
    # Small models (fast, good for testing)
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"
    PARAPHRASE_MULTILINGUAL_MINI = "paraphrase-multilingual-MiniLM-L12-v2"

    # Tiny models (very fast, basic quality)
    ALL_MINILM_L12_V2 = "all-MiniLM-L12-v2"
    DISTILBERT_BASE_NLI_STSB_MEAN_TOKENS = "distilbert-base-nli-stsb-mean-tokens"

    # Specialized models
    MSMARCO_DISTILBERT_BASE_V4 = "msmarco-distilbert-base-v4"
    MULTI_QA_MINILM_L6_COS_V1 = "multi-qa-MiniLM-L6-cos-v1"


class GitHubConfig(Enum):
    BASE_URL = "https://codeload.github.com"
    TIMEOUT = 30
    MAX_FILE_SIZE = 10_000_000
    MAX_FILES = 1000
    MAX_TOTAL_SIZE = 50_000_000


class FileProcessingConfig(Enum):
    MAX_FILE_SIZE = 10_000_000  # 10MB per file
    MAX_CONTENT_SIZE = 5_000_000  # 5MB content
    ALLOWED_EXTENSIONS = {"md", "mdx", "txt", "rst", "adoc"}
    BLOCKED_EXTENSIONS = {"exe", "bat", "sh", "py", "js", "jar", "dll", "so"}


# OpenAI configuration
API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=API_KEY)
