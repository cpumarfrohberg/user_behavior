import pytest

from rag_agent.models import RAGAnswer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_initialization(initialized_agent):
    """Test agent can be initialized"""
    assert initialized_agent.agent is not None
    assert initialized_agent.search_index is not None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_makes_1_2_searches(initialized_agent):
    """Test agent makes 1-2 tool calls (simplified for speed)"""
    question = "What are common user frustration patterns?"

    answer, tool_calls = await initialized_agent.query(question)

    # Verify tool call count (1-2 searches for speed optimization)
    assert 1 <= len(tool_calls) <= 2, f"Expected 1-2 tool calls, got {len(tool_calls)}"

    # Verify all calls are search_documents
    assert all(
        call["tool_name"] == "search_documents" for call in tool_calls
    ), "All tool calls should be search_documents"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_not_more_than_2_searches(initialized_agent):
    """Test agent doesn't make excessive searches (speed optimization)"""
    question = "examples of incorrect LLM responses"

    answer, tool_calls = await initialized_agent.query(question)

    assert len(tool_calls) <= 2, f"Expected at most 2 tool calls, got {len(tool_calls)}"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_returns_structured_output(initialized_agent):
    """Test agent returns valid RAGAnswer structure"""
    question = "What are common user frustration patterns?"

    answer, tool_calls = await initialized_agent.query(question)

    # Verify it's a RAGAnswer
    assert isinstance(answer, RAGAnswer)

    # Verify required fields
    assert answer.answer is not None
    assert isinstance(answer.answer, str)
    assert len(answer.answer) > 0

    assert 0.0 <= answer.confidence <= 1.0
    assert isinstance(answer.sources_used, list)
    assert isinstance(answer.reasoning, (str, type(None)))


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_includes_sources(initialized_agent):
    """Test agent includes sources in output"""
    question = "How do users express satisfaction?"

    answer, tool_calls = await initialized_agent.query(question)

    assert len(answer.sources_used) > 0, "Agent should include sources"
    assert all(isinstance(source, str) for source in answer.sources_used)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_tool_calls_are_tracked(initialized_agent):
    """Test tool calls are properly tracked"""
    question = "What usability issues do users report?"

    answer, tool_calls = await initialized_agent.query(question)

    assert len(tool_calls) > 0, "Tool calls should be tracked"

    # Verify tool call structure
    for call in tool_calls:
        assert "tool_name" in call
        assert "args" in call
        assert call["tool_name"] == "search_documents"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_all_tool_calls_are_search_documents(initialized_agent):
    """Test all tool calls use search_documents"""
    question = "What are common user frustration patterns?"

    answer, tool_calls = await initialized_agent.query(question)

    for call in tool_calls:
        assert (
            call["tool_name"] == "search_documents"
        ), f"Expected search_documents, got {call['tool_name']}"
