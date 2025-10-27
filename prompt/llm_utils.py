# LLM utilities for user behavior RAG system with Ollama integration
import logging
from typing import Optional

from config import (
    DEFAULT_RAG_MODEL,
    ollama_client,
)

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Simple Ollama LLM integration for user behavior RAG system"""

    def __init__(self, model: str = DEFAULT_RAG_MODEL):
        self.model = model
        self.client = ollama_client

    def query(self, prompt: str, temperature: float = 0.7) -> str:
        """Query Ollama and return simple text response"""
        try:
            logger.debug(f"Querying Ollama model {self.model}")

            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": 1000,  # Limit response length
                },
            )

            return response.get("response", "").strip()

        except Exception as e:
            logger.error(f"Error querying Ollama: {e}")
            raise


def query_ollama(
    prompt: str, model: str = DEFAULT_RAG_MODEL, temperature: float = 0.7
) -> str:
    """Convenience function to query Ollama"""
    llm = OllamaLLM(model)
    return llm.query(prompt, temperature)
