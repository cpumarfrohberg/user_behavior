# Judge LLM Design Proposal

## Overview

The Judge LLM is an evaluation system that assesses the quality of RAG agent answers. It uses a separate LLM (`phi3:mini`) to evaluate answer quality, relevance, completeness, and source attribution.

## Architecture

### Components

1. **JudgeScore Model** (`source/models.py` or `rag_agent/judge.py`)
   - Structured output for judge evaluation
   - Scores for different dimensions of answer quality

2. **JudgeLLM Class** (`rag_agent/judge.py`)
   - Uses `pydantic-ai` Agent with structured output
   - Integrates with Ollama (same pattern as RAG agent)
   - Evaluates `RAGAnswer` objects

3. **Evaluation Criteria**
   - Relevance: Does the answer address the question?
   - Completeness: Is the answer thorough enough?
   - Accuracy: Are the facts correct based on sources?
   - Source Attribution: Are sources properly cited?
   - Coherence: Is the answer well-structured and clear?

## Design Decisions

### Why `pydantic-ai`?
- **Consistency**: RAG agent uses `pydantic-ai`, so Judge should too
- **Structured Output**: Ensures reliable JSON evaluation scores
- **Ollama Integration**: Same pattern as RAG agent (OpenAIChatModel + OpenAIProvider)

### Why `phi3:mini`?
- **Strong Reasoning**: Better at evaluation tasks than generation
- **No Tools Needed**: Judge doesn't need tool calling capability
- **Lower Temperature**: Already configured (`DEFAULT_JUDGE_TEMPERATURE = 0.1`)
- **Fast**: Smaller model for quick evaluations

### Why Separate from RAG Agent?
- **Different Purpose**: RAG generates, Judge evaluates
- **Different Models**: RAG needs tools (`llama3.2:3b`), Judge doesn't (`phi3:mini`)
- **Independent Evaluation**: Can evaluate any RAG answer, not just from our agent

## Data Models

### JudgeScore Model

```python
class JudgeScore(BaseModel):
    """Structured evaluation score from Judge LLM"""

    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0 to 1.0)"
    )

    relevance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How relevant is the answer to the question?"
    )

    completeness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How complete is the answer?"
    )

    accuracy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How accurate are the facts based on sources?"
    )

    source_attribution: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Are sources properly cited and used?"
    )

    coherence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Is the answer well-structured and clear?"
    )

    reasoning: str = Field(
        ...,
        description="Brief explanation of the evaluation"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Judge's confidence in this evaluation"
    )
```

## Implementation Structure

### File: `rag_agent/judge.py`

```python
# rag_agent/judge.py
"""
Judge LLM for evaluating RAG agent answers
"""

import logging
from typing import Optional

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_TEMPERATURE,
    OLLAMA_HOST,
)
from source.models import RAGAnswer
from rag_agent.models import JudgeScore  # New model

logger = logging.getLogger(__name__)


class JudgeLLM:
    """Judge LLM for evaluating RAG agent answer quality"""

    def __init__(
        self,
        model: str = DEFAULT_JUDGE_MODEL,
        temperature: float = DEFAULT_JUDGE_TEMPERATURE,
    ):
        """
        Initialize Judge LLM

        Args:
            model: Ollama model name (default: phi3:mini)
            temperature: Temperature for evaluation (default: 0.1)
        """
        self.model = model
        self.temperature = temperature
        self.agent: Optional[Agent] = None

    def initialize(self) -> None:
        """Initialize the pydantic-ai agent"""
        # Judge instructions (evaluation-focused)
        instructions = self._get_judge_instructions()

        # Create model (same pattern as RAG agent)
        model = OpenAIChatModel(
            model_name=self.model,
            provider=OpenAIProvider(
                base_url=f"{OLLAMA_HOST}/v1",
            ),
            temperature=self.temperature,
        )

        # Create agent with structured output
        self.agent = Agent(
            name="judge_llm",
            model=model,
            instructions=instructions,
            output_type=JudgeScore,
        )

        logger.info(f"Judge LLM initialized with model: {self.model}")

    def _get_judge_instructions(self) -> str:
        """Get judge evaluation instructions"""
        return """
You are a Judge LLM that evaluates the quality of RAG (Retrieval Augmented Generation) answers.

Your role is to evaluate answers based on:
1. **Relevance**: Does the answer directly address the question?
2. **Completeness**: Is the answer thorough and comprehensive?
3. **Accuracy**: Are the facts correct based on the provided sources?
4. **Source Attribution**: Are sources properly cited and used?
5. **Coherence**: Is the answer well-structured, clear, and easy to understand?

EVALUATION CRITERIA:
- **Relevance (0.0-1.0)**: How well does the answer match the question?
  - 1.0: Perfect match, directly answers the question
  - 0.5: Partially relevant, addresses some aspects
  - 0.0: Not relevant, doesn't answer the question

- **Completeness (0.0-1.0)**: How thorough is the answer?
  - 1.0: Comprehensive, covers all important aspects
  - 0.5: Partially complete, missing some details
  - 0.0: Incomplete, major gaps in information

- **Accuracy (0.0-1.0)**: How accurate are the facts?
  - 1.0: All facts correct based on sources
  - 0.5: Mostly correct, some minor inaccuracies
  - 0.0: Major factual errors or contradictions

- **Source Attribution (0.0-1.0)**: Are sources properly used?
  - 1.0: Sources well-cited and relevant
  - 0.5: Some sources cited, but could be better
  - 0.0: Poor or no source attribution

- **Coherence (0.0-1.0)**: Is the answer well-structured?
  - 1.0: Clear, well-organized, easy to follow
  - 0.5: Somewhat clear, minor organization issues
  - 0.0: Confusing, poorly structured, hard to understand

OUTPUT FORMAT:
You MUST return a JSON object with these exact fields:
- "overall_score": Weighted average of all dimensions (0.0 to 1.0)
- "relevance": Relevance score (0.0 to 1.0)
- "completeness": Completeness score (0.0 to 1.0)
- "accuracy": Accuracy score (0.0 to 1.0)
- "source_attribution": Source attribution score (0.0 to 1.0)
- "coherence": Coherence score (0.0 to 1.0)
- "reasoning": Brief explanation of your evaluation
- "confidence": Your confidence in this evaluation (0.0 to 1.0)

Example JSON format:
{
  "overall_score": 0.85,
  "relevance": 0.9,
  "completeness": 0.8,
  "accuracy": 0.9,
  "source_attribution": 0.85,
  "coherence": 0.8,
  "reasoning": "The answer is highly relevant and accurate, with good source attribution. Minor gaps in completeness.",
  "confidence": 0.9
}
""".strip()

    async def evaluate(
        self,
        question: str,
        answer: RAGAnswer,
        sources: Optional[list[dict]] = None,
    ) -> JudgeScore:
        """
        Evaluate a RAG answer

        Args:
            question: Original question asked
            answer: RAGAnswer to evaluate
            sources: Optional list of source documents (for context)

        Returns:
            JudgeScore with evaluation metrics
        """
        if self.agent is None:
            raise RuntimeError("Judge not initialized. Call initialize() first.")

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(question, answer, sources)

        # Run judge agent
        logger.info(f"Evaluating answer for question: {question[:100]}...")
        result = await self.agent.run(prompt)

        return result.output

    def _build_evaluation_prompt(
        self,
        question: str,
        answer: RAGAnswer,
        sources: Optional[list[dict]] = None,
    ) -> str:
        """Build evaluation prompt for judge"""
        prompt = f"""
QUESTION:
{question}

ANSWER TO EVALUATE:
{answer.answer}

SOURCE IDENTIFIERS USED:
{', '.join(answer.sources_used) if answer.sources_used else 'None'}

CONFIDENCE (from RAG agent):
{answer.confidence:.2f}

REASONING (from RAG agent):
{answer.reasoning if answer.reasoning else 'No reasoning provided'}
"""

        # Add source context if available
        if sources:
            prompt += "\nSOURCE DOCUMENTS (for reference):\n"
            for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
                prompt += f"\n[{i}] {source.get('title', 'No title')}\n"
                prompt += f"{source.get('content', '')[:200]}...\n"

        prompt += "\n\nEvaluate this answer based on the criteria above."

        return prompt
```

## Integration Points

### 1. CLI Command

Add `judge-evaluate` command to `cli.py`:

```python
@app.command()
def judge_evaluate(
    question: str = typer.Argument(..., help="Original question"),
    answer_file: Optional[str] = typer.Option(None, "--answer-file", "-f", help="JSON file with RAGAnswer"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed scores"),
):
    """Evaluate a RAG answer using Judge LLM"""
    # Load answer from file or use agent_ask result
    # Initialize judge
    # Run evaluation
    # Display scores
```

### 2. Test Integration

Add judge evaluation to test suite:

```python
# tests/rag_agent/test_judge.py
async def test_judge_evaluation():
    """Test judge evaluation of RAG answer"""
    judge = JudgeLLM()
    await judge.initialize()

    answer = RAGAnswer(
        answer="Test answer",
        confidence=0.8,
        sources_used=["source1"],
        reasoning="Test reasoning",
    )

    score = await judge.evaluate("Test question", answer)

    assert 0.0 <= score.overall_score <= 1.0
    assert 0.0 <= score.relevance <= 1.0
    # ... more assertions
```

### 3. Evaluation Pipeline

Use judge for batch evaluation:

```python
# evals/judge_evaluation.py
async def evaluate_rag_answers(
    ground_truth: list[dict],
    agent: RAGAgent,
    judge: JudgeLLM,
) -> list[dict]:
    """Evaluate RAG answers against ground truth using Judge"""
    results = []

    for gt_item in ground_truth:
        question = gt_item["question"]

        # Get RAG answer
        answer, _ = await agent.query(question)

        # Get judge evaluation
        judge_score = await judge.evaluate(question, answer)

        results.append({
            "question": question,
            "judge_score": judge_score,
            "rag_answer": answer,
        })

    return results
```

## Configuration

### Environment Variables

Already configured in `config/__init__.py`:
- `DEFAULT_JUDGE_MODEL = ModelType.PHI3_MINI`
- `DEFAULT_JUDGE_TEMPERATURE = 0.1`
- `OLLAMA_HOST` (from environment)

### Instructions

Add judge instructions to `config/instructions.py`:

```python
# In InstructionsConfig.INSTRUCTIONS
InstructionType.JUDGE_LLM: """
[Judge instructions here - same as _get_judge_instructions()]
""",
```

## Usage Examples

### Example 1: Evaluate Single Answer

```python
from rag_agent.judge import JudgeLLM
from source.models import RAGAnswer

# Initialize judge
judge = JudgeLLM()
await judge.initialize()

# Create RAG answer
answer = RAGAnswer(
    answer="User frustration patterns include...",
    confidence=0.85,
    sources_used=["question_123", "question_456"],
    reasoning="Found relevant discussions about user behavior",
)

# Evaluate
score = await judge.evaluate(
    question="What are common user frustration patterns?",
    answer=answer,
)

print(f"Overall Score: {score.overall_score:.2f}")
print(f"Relevance: {score.relevance:.2f}")
print(f"Reasoning: {score.reasoning}")
```

### Example 2: Batch Evaluation

```python
# Evaluate multiple answers
scores = []
for question, answer in zip(questions, answers):
    score = await judge.evaluate(question, answer)
    scores.append(score)

avg_score = sum(s.overall_score for s in scores) / len(scores)
print(f"Average Score: {avg_score:.2f}")
```

## Testing Strategy

### Unit Tests

1. **Judge Initialization**
   - Test agent creation
   - Test model configuration
   - Test instructions loading

2. **Evaluation Logic**
   - Test prompt building
   - Test score validation
   - Test edge cases (empty answer, no sources, etc.)

3. **Integration Tests**
   - Test with real Ollama model
   - Test with actual RAG answers
   - Test score consistency

### Test File: `tests/rag_agent/test_judge.py`

```python
import pytest
from rag_agent.judge import JudgeLLM
from source.models import RAGAnswer

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)
async def test_judge_evaluation(initialized_judge, sample_rag_answer):
    """Test judge evaluation of RAG answer"""
    score = await initialized_judge.evaluate(
        question="Test question",
        answer=sample_rag_answer,
    )

    assert 0.0 <= score.overall_score <= 1.0
    assert 0.0 <= score.relevance <= 1.0
    assert score.reasoning is not None
```

## Performance Considerations

1. **Model Choice**: `phi3:mini` is fast and doesn't need tools
2. **Temperature**: Low (0.1) for consistent evaluations
3. **Batch Processing**: Can evaluate multiple answers sequentially
4. **Caching**: Consider caching evaluations for same question/answer pairs

## Future Enhancements

1. **Multi-Judge Consensus**: Average scores from multiple judge models
2. **Fine-Tuning**: Fine-tune judge on labeled evaluation data
3. **Confidence Calibration**: Calibrate judge confidence scores
4. **A/B Testing**: Compare different RAG configurations using judge scores

## Dependencies

- `pydantic-ai`: For structured output (already installed)
- `pydantic`: For models (already installed)
- `ollama`: For local model execution (already configured)

## Implementation Steps

1. ✅ Design proposal (this document)
2. ⏭️ Create `JudgeScore` model in `source/models.py`
3. ⏭️ Create `JudgeLLM` class in `rag_agent/judge.py`
4. ⏭️ Add judge instructions to `config/instructions.py`
5. ⏭️ Add CLI command `judge-evaluate` to `cli.py`
6. ⏭️ Create tests in `tests/rag_agent/test_judge.py`
7. ⏭️ Add evaluation pipeline in `evals/judge_evaluation.py`
8. ⏭️ Update documentation

## Questions to Resolve

1. **Model Choice**: Should we use `phi3:mini` or test with `llama3.2:3b` for judge?
2. **Source Context**: Should judge see full source documents or just identifiers?
3. **Weighting**: Should `overall_score` be simple average or weighted?
4. **Ground Truth**: How should judge scores compare to ground truth evaluation?
