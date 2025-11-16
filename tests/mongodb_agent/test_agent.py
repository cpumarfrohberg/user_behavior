import pytest

from mongodb_agent.models import SearchAnswer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_initialization(initialized_agent):
    """Test agent can be initialized"""
    assert initialized_agent.agent is not None
    assert initialized_agent.collection is not None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_makes_1_2_searches(initialized_agent):
    """Test agent makes 1-2 tool calls (simplified for speed)"""
    question = "What are common user frustration patterns?"

    result = await initialized_agent.query(question)

    # Verify tool call count (1-2 searches for speed optimization)
    assert (
        1 <= len(result.tool_calls) <= 2
    ), f"Expected 1-2 tool calls, got {len(result.tool_calls)}"

    # Verify all calls are search_mongodb
    assert all(
        call["tool_name"] == "search_mongodb" for call in result.tool_calls
    ), "All tool calls should be search_mongodb"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_not_more_than_2_searches(initialized_agent):
    """Test agent doesn't make excessive searches (speed optimization)"""
    question = "examples of incorrect LLM responses"

    result = await initialized_agent.query(question)

    assert (
        len(result.tool_calls) <= 2
    ), f"Expected at most 2 tool calls, got {len(result.tool_calls)}"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_returns_structured_output(initialized_agent):
    """Test agent returns valid RAGAnswer structure"""
    question = "What are common user frustration patterns?"

    result = await initialized_agent.query(question)

    # Verify it's a SearchAgentResult
    from mongodb_agent.models import SearchAgentResult

    assert isinstance(result, SearchAgentResult)

    # Verify answer structure
    assert isinstance(result.answer, SearchAnswer)
    assert result.answer.answer is not None
    assert isinstance(result.answer.answer, str)
    assert len(result.answer.answer) > 0

    assert 0.0 <= result.answer.confidence <= 1.0
    assert isinstance(result.answer.sources_used, list)
    assert isinstance(result.answer.reasoning, (str, type(None)))

    # Verify tool_calls
    assert isinstance(result.tool_calls, list)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_agent_includes_sources(initialized_agent):
    """Test agent includes sources in output"""
    question = "How do users express satisfaction?"

    result = await initialized_agent.query(question)

    assert len(result.answer.sources_used) > 0, "Agent should include sources"
    assert all(isinstance(source, str) for source in result.answer.sources_used)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_tool_calls_are_tracked(initialized_agent):
    """Test tool calls are properly tracked"""
    question = "What usability issues do users report?"

    result = await initialized_agent.query(question)

    assert len(result.tool_calls) > 0, "Tool calls should be tracked"

    # Verify tool call structure
    for call in result.tool_calls:
        assert "tool_name" in call
        assert "args" in call
        assert call["tool_name"] == "search_mongodb"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(120)  # 2 minute timeout for LLM calls
async def test_all_tool_calls_are_search_documents(initialized_agent):
    """Test all tool calls use search_documents"""
    question = "What are common user frustration patterns?"

    result = await initialized_agent.query(question)

    for call in result.tool_calls:
        assert (
            call["tool_name"] == "search_mongodb"
        ), f"Expected search_mongodb, got {call['tool_name']}"
