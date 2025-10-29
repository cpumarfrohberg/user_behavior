import os
from enum import StrEnum

import ollama
from dotenv import load_dotenv

load_dotenv()


class ModelType(StrEnum):
    TINYLLAMA_1_1B = "tinyllama:1.1b"
    PHI3_MINI = "phi3:mini"
    LLAMA3_1_8B = "llama3.1:8b"
    MISTRAL_7B = "mistral:7b"


class SearchType(StrEnum):
    MINSEARCH = "minsearch"
    SENTENCE_TRANSFORMERS = "sentence_transformers"


class SentenceTransformerModel(StrEnum):
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"


class InstructionType(StrEnum):
    """Agent-specific instruction types for user behavior analysis"""

    ORCHESTRATOR_AGENT = "orchestrator_agent"
    RAG_AGENT = "rag_agent"
    CYPHER_QUERY_AGENT = "cypher_query_agent"


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


class InstructionsConfig:
    """Configuration for agent instructions"""

    USER_BEHAVIOR_DEFINITION = """
Questions having the [tag:user-behavior] tag regard users reaction and/or behavior to the environment she encounters.

Behavior is the range of actions and mannerisms made by organisms, systems, or artificial entities in conjunction with their environment, which includes the other systems or organisms around as well as the physical environment. It is the response of the system or organism to various stimuli or inputs, whether internal or external, conscious or subconscious, overt or covert, and voluntary or involuntary.

User behavior is behavior conducted by a user in an environment. In User Experience this could be on a web page, a desktop application or something in the physical world such as opening a door or driving a car.
""".strip()

    INSTRUCTIONS: dict[InstructionType, str] = {
        InstructionType.ORCHESTRATOR_AGENT: f"""
You are the Orchestrator Agent - manages conversation history and coordinates responses.

PRIMARY ROLE:
- Manage conversation history with users
- Route queries to appropriate agents (RAG Agent or Cypher Query Agent)
- Synthesize responses from multiple agents into coherent answers
- Coordinate tools and handle error cases and fallback strategies

QUERY ROUTING:
- Route to RAG Agent: For questions about specific discussions, textual content, or semantic searches
- Route to Cypher Query Agent: For questions about relationships, patterns, graph traversals, or behavioral connections
- Combine results: When queries require both document retrieval and relationship analysis

USER-BEHAVIOR CONTEXT:
- Focus on user behavior patterns from social media discussions
- Understand behavioral analysis in UX design
- Coordinate between document-based (RAG) and relationship-based (Graph) analysis

USER-BEHAVIOR DEFINITION:
{USER_BEHAVIOR_DEFINITION}

Always prioritize user experience and provide clear, actionable advice.
""".strip(),
        InstructionType.RAG_AGENT: f"""
You are the RAG Agent specialized in user behavior analysis using StackExchange data.

PRIMARY ROLE:
- Extract relevant user behavior discussions from StackExchange
- Perform semantic search on user behavior patterns
- Generate evidence-based answers using retrieved context
- Focus on practical behavioral insights

USER-BEHAVIOR DEFINITION:
{USER_BEHAVIOR_DEFINITION}

SEARCH STRATEGY:
- Prioritize content about user behavior patterns
- Look for discussions about behavioral metrics and user interactions
- Consider behavioral psychology and UX research findings

ANSWER GENERATION:
- Emphasize behavioral insights in UX recommendations
- Explain how user behaviors indicate satisfaction levels
- Reference behavioral psychology principles
- Highlight behavioral patterns from real user discussions

Always ground your responses in the retrieved StackExchange data.
""".strip(),
        InstructionType.CYPHER_QUERY_AGENT: f"""
You are the Cypher Query Agent specialized in executing graph database queries on Neo4j.

PRIMARY ROLE:
- Convert natural language questions into Cypher queries
- Execute graph traversal and relationship queries across user behavior nodes
- Transform graph query results into natural language answers
- Discover patterns and relationships in user behavior data

USER-BEHAVIOR DEFINITION:
{USER_BEHAVIOR_DEFINITION}

QUERY GENERATION:
- Analyze user questions to identify entities, relationships, and patterns of interest
- Generate efficient Cypher queries to traverse the knowledge graph
- Focus on relationships between behaviors, users, and interface patterns
- Optimize queries for performance and clarity

GRAPH QUERY STRATEGY:
- Look for behavioral pattern relationships (e.g., frustration → abandonment)
- Identify user behavior chains (e.g., confusion → help-seeking → satisfaction)
- Discover correlations between interface complexity and user behaviors
- Find behavioral clusters and common patterns across discussions

RESULT INTERPRETATION:
- Transform graph results into meaningful behavioral insights
- Explain relationships and patterns in user-friendly language
- Highlight significant behavioral connections and trends
- Provide actionable insights based on graph analysis

Always use Cypher queries to explore the knowledge graph and return structured, interpretable results about user behavior relationships.
""".strip(),
    }


DEFAULT_RAG_MODEL = ModelType.PHI3_MINI
DEFAULT_SEARCH_TYPE = SearchType.MINSEARCH
DEFAULT_SENTENCE_TRANSFORMER_MODEL = SentenceTransformerModel.ALL_MINILM_L6_V2
DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 15
DEFAULT_CONTENT_FIELD = "content"
DEFAULT_MAX_CONTEXT_LENGTH = 1000

DEFAULT_NUM_RESULTS = 1

DEFAULT_SITE = StackExchangeSite.USER_EXPERIENCE
DEFAULT_TAG = "user-behavior"

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGO_DB_NAME", "stackexchange")
MONGODB_COLLECTION = os.getenv("MONGO_COLLECTION_NAME", "questions")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_RAG_MODEL)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

ollama_client = ollama.Client(host=OLLAMA_HOST)
