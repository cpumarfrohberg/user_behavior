# Prompt construction utilities
import json
from typing import Any, Dict, List

from .models import SearchResult


def build_prompt(
    question: str,
    search_results: List[Dict[str, Any]],
    instruction_type: str = "faq_assistant",
) -> str:
    """
    Build a structured prompt for the LLM using search results.

    Converts raw search results into a structured format and creates a prompt
    that instructs the LLM to respond in the RAGAnswer format.

    Args:
        question: The user's question to be answered
        search_results: List of relevant document dictionaries from search
        instruction_type: Type of instruction/prompt template to use

    Returns:
        Formatted prompt string ready for LLM processing
    """

    # Convert search results to structured format
    structured_results = []
    for result in search_results:
        structured_results.append(
            SearchResult(
                content=result.get("content", ""),
                filename=result.get("filename", "unknown"),
                title=result.get("title"),
                similarity_score=result.get("similarity_score"),
            )
        )

    # Create the structured prompt
    prompt = f"""
Answer the following question based on the provided context documents.

Question: {question}

Context Documents:
{json.dumps([result.dict() for result in structured_results], indent=2)}

Please provide a structured response with:
1. A clear answer to the question
2. Your confidence level (0.0 to 1.0)
3. List of source filenames you used
4. Brief reasoning for your answer (optional)

Respond in the exact format specified by the RAGAnswer model.
"""

    return prompt
