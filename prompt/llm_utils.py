# LLM utilities for user behavior RAG system with Ollama integration
import logging

from config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RAG_MODEL,
    DEFAULT_TEMPERATURE,
    ollama_client,
)

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Simple Ollama LLM integration for user behavior RAG system"""

    def __init__(self, model: str = DEFAULT_RAG_MODEL):
        self.model = model
        self.client = ollama_client

    def query(self, prompt: str, temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Query Ollama and return simple text response"""
        try:
            logger.debug(f"Querying Ollama model {self.model}")

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": DEFAULT_MAX_TOKENS,
                },
            )

            return response.get("response", "").strip()

        except Exception as e:
            logger.error(f"Error querying Ollama: {e}")
            raise
