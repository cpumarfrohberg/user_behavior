# Text-based RAG implementation for GitHub repository analysis
from typing import Callable, List

from minsearch import Index
from sentence_transformers import SentenceTransformer

from config import (
    InstructionType,
    SearchType,
    SentenceTransformerModel,
    openai_client,
)
from fetch_prep_data.parser import parse_data
from fetch_prep_data.reader import read_github_data
from prompt.chunking_utils import chunk_documents
from prompt.llm_utils import query_with_context
from prompt.vector_search import create_vector_index


class TextRAG:
    """RAG implementation for GitHub repository analysis with multiple search types"""

    def __init__(
        self,
        search_type: str = SearchType.TEXT.value,
        model_name: str = SentenceTransformerModel.ALL_MINILM_L6_V2.value,
        text_fields: List[str] | None = None,
    ):
        self.search_type = search_type
        self.model_name = model_name
        self.text_fields = text_fields or [
            "content",
            "filename",
            "title",
            "description",
        ]
        self.documents = []
        self.chunks = []
        self.index = None
        self.embedder = None

        # Initialize embedder if using SentenceTransformers
        if search_type == SearchType.VECTOR_SENTENCE_TRANSFORMERS.value:
            try:
                self.embedder = SentenceTransformer(model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for vector_sentence_transformers search type. "
                    "Install it with: pip install sentence-transformers"
                )

    def load_repository(
        self,
        repo_owner: str,
        repo_name: str,
        allowed_extensions: set | None = None,
        filename_filter: Callable | None = None,
        chunk_size: int | None = None,
        chunk_step: int | None = None,
    ):
        """Load and process GitHub repository data"""

        # Step 1: Fetch GitHub data
        github_data = read_github_data(
            repo_owner=repo_owner,
            repo_name=repo_name,
            allowed_extensions=allowed_extensions,
            filename_filter=filename_filter,
        )

        # Step 2: Parse the data
        parsed_data = parse_data(github_data)

        # Step 3: Chunk the documents
        self.chunks = chunk_documents(parsed_data, size=chunk_size, step=chunk_step)
        print(f"📝 Created {len(self.chunks)} document chunks")

        # Step 4: Create appropriate index based on search type
        if self.search_type == SearchType.TEXT.value:
            # Standard text search with minsearch
            self.index = Index(text_fields=self.text_fields)
            self.index.fit(self.chunks)
        elif self.search_type == SearchType.VECTOR_MINSEARCH.value:
            # Minsearch with embeddings (placeholder for future implementation)
            self.index = Index(text_fields=self.text_fields)
            self.index.fit(self.chunks)
            print("⚠️  Vector minsearch not yet implemented, using text search")
        elif self.search_type == SearchType.VECTOR_SENTENCE_TRANSFORMERS.value:
            # SentenceTransformers vector search
            if self.embedder is None:
                raise ValueError("SentenceTransformer model not initialized")
            self.index = create_vector_index(self.chunks, self.embedder)
        else:
            raise ValueError(f"Unsupported search type: {self.search_type}")

        self.documents = parsed_data

    def query(
        self, question: str, instruction_type: str = InstructionType.FAQ_ASSISTANT.value
    ) -> str:
        """Query the repository using text-based search"""
        if not self.index:
            raise ValueError("No repository loaded. Call load_repository() first.")

        return query_with_context(
            question=question,
            index=self.index,
            instruction_type=instruction_type,
            openai_client=openai_client,
        )
