# Core TextRAG system for user behavior analysis
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONTENT_FIELD,
    DEFAULT_MAX_CONTEXT_LENGTH,
    DEFAULT_NUM_RESULTS,
    DEFAULT_RAG_MODEL,
    DEFAULT_SEARCH_TYPE,
    MONGODB_DB,
    MONGODB_URI,
    InstructionType,
    SearchType,
)
from prompt.llm_utils import OllamaLLM
from search.search_utils import SearchIndex
from search.simple_chunking import chunk_documents
from source.models import RAGAnswer

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """Configuration for RAG system"""

    search_type: str = DEFAULT_SEARCH_TYPE
    instruction_type: InstructionType = InstructionType.RAG_AGENT
    ollama_model: str = DEFAULT_RAG_MODEL
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    max_context_length: int = DEFAULT_MAX_CONTEXT_LENGTH
    mongo_uri: str = MONGODB_URI
    database: str = MONGODB_DB
    collection: str = "posts"


class TextRAG:
    """Core RAG system for user behavior queries with Ollama integration"""

    def __init__(
        self,
        config: RAGConfig,
        search_index: Optional[SearchIndex] = None,
        llm: Optional[OllamaLLM] = None,
    ):
        self.config = config

        # Use provided dependencies or create defaults
        self.search_index = search_index or SearchIndex(config.search_type)
        self.llm = llm or OllamaLLM(config.ollama_model)

        logger.info(
            f"Initialized TextRAG with {config.search_type} search and {config.ollama_model} model"
        )

    def load_from_mongodb(self, should_chunk: bool = True) -> None:
        """Load documents from MongoDB using proper parsing"""
        try:
            logger.info(
                f"Loading documents from MongoDB: {self.config.database}.{self.config.collection}"
            )

            # Connect to MongoDB using config
            client = MongoClient(self.config.mongo_uri)
            db = client[self.config.database]
            collection_obj = db[self.config.collection]

            # Load ALL documents (not just body/title)
            docs = list(collection_obj.find({}, {"_id": 0}))
            logger.info(f"Loaded {len(docs)} documents from MongoDB")

            # Use proper parser to convert MongoDB docs to RAG format
            documents = self._parse_mongodb_documents(docs)
            logger.info(f"Parsed {len(documents)} documents for RAG")

            client.close()

            # Load documents into RAG system
            self.load_documents(documents, should_chunk=should_chunk)

        except Exception as e:
            logger.error(f"Error loading from MongoDB: {e}")
            raise

    def _parse_mongodb_documents(
        self, docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Private method to convert MongoDB docs to RAG format"""
        parsed_docs = []
        for doc in docs:
            # Combine title and body for content
            content_parts = []
            if doc.get("title"):
                content_parts.append(doc["title"])
            if doc.get("body"):
                content_parts.append(doc["body"])

            parsed_docs.append(
                {
                    "content": " ".join(content_parts),
                    "title": doc.get("title", ""),
                    "source": f"question_{doc.get('question_id', 'unknown')}",
                    "tags": doc.get("tags", []),
                }
            )
        return parsed_docs

    def load_documents(
        self,
        documents: List[Dict[str, Any]],
        should_chunk: bool = True,
    ) -> None:
        """Load documents into the RAG system with simple chunking"""
        try:
            logger.info(f"Loading {len(documents)} documents into RAG system")
            print(f"🔍 DEBUG: Starting to load {len(documents)} documents...")

            # Limit documents to prevent memory issues
            max_docs = 500  # Further limit for processing
            if len(documents) > max_docs:
                print(f"⚠️  Limiting to {max_docs} documents to prevent memory issues")
                documents = documents[:max_docs]

            if should_chunk:
                print("🔍 DEBUG: Chunking documents with simple approach...")
                # Use simple chunking function
                chunked_docs = chunk_documents(
                    documents, self.config.chunk_size, self.config.chunk_overlap
                )
                logger.info(f"Chunked documents into {len(chunked_docs)} chunks")
                print(f"🔍 DEBUG: Created {len(chunked_docs)} chunks")
            else:
                chunked_docs = documents
                print("🔍 DEBUG: Skipping chunking, using original documents")

            # Add to search index with progress tracking
            print("🔍 DEBUG: Adding documents to search index...")
            self.search_index.add_documents(chunked_docs)
            print("🔍 DEBUG: Documents added to search index successfully!")

            logger.info(
                f"Successfully loaded {len(chunked_docs)} documents into search index"
            )

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            print(f"❌ DEBUG: Error loading documents: {e}")
            raise

    def query(
        self,
        question: str,
        num_results: int = DEFAULT_NUM_RESULTS,
        temperature: float = 0.3,
        include_metadata: bool = True,
    ) -> RAGAnswer:
        """Query the RAG system and return structured response"""
        try:
            logger.info(f"Processing query: {question[:100]}...")
            print(f"🔍 DEBUG: Starting query processing for: {question[:50]}...")

            # Search for relevant documents
            print("🔍 DEBUG: Searching for relevant documents...")
            search_results = self.search_index.search(
                query=question,
                num_results=num_results,
            )
            print(
                f"🔍 DEBUG: Found {len(search_results) if search_results else 0} search results"
            )

            if not search_results:
                logger.warning("No search results found for query")
                return RAGAnswer(
                    answer="I couldn't find any relevant information to answer your question.",
                    confidence=0.0,
                    sources_used=[],
                    reasoning="No search results found",
                )

            # Build simple prompt
            print("🔍 DEBUG: Building prompt...")
            context_text = "\n\n".join(
                [
                    f"Source: {doc.get('source', 'unknown')}\nContent: {doc.get('content', '')}"
                    for doc in search_results[:3]  # Limit to top 3 results
                ]
            )

            prompt = f"""You are a user behavior expert. Answer the question based on the provided context about user behavior patterns.

Question: {question}

Context:
{context_text}

Provide a clear, helpful answer about user behavior patterns based on the context provided."""
            print(f"🔍 DEBUG: Prompt built, length: {len(prompt)} characters")

            # Query LLM with simple response
            print("🔍 DEBUG: Calling Ollama LLM...")
            response_text = self.llm.query(prompt, temperature=temperature)
            print("🔍 DEBUG: Ollama LLM call completed!")

            # Create simple RAGAnswer response
            rag_answer = RAGAnswer(
                answer=response_text,
                confidence=0.8,  # Simple confidence score
                sources_used=[
                    doc.get("source", "unknown") for doc in search_results[:3]
                ],
                reasoning="Generated from StackExchange user behavior discussions",
            )

            logger.info(f"Generated answer with confidence {rag_answer.confidence}")
            return rag_answer

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"❌ DEBUG: Error in query processing: {e}")
            # Return fallback response
            return RAGAnswer(
                answer=f"I encountered an error while processing your question: {str(e)}",
                confidence=0.1,
                sources_used=["error"],
                reasoning="Error occurred during processing",
            )
