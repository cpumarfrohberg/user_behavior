# OpenAI Migration Plan

## Overview

This document outlines the steps needed to migrate from Ollama to OpenAI models, and to continue debugging the model output capture issue.

## Current State

- **Ollama Integration**: Currently using Ollama via `ollama` package and `pydantic-ai` with OpenAI-compatible interface
- **Two LLM Usage Points**:
  1. `prompt/llm_utils.py` - `OllamaLLM` class for simple RAG queries (used by `TextRAG`)
  2. `rag_agent/agent.py` - `pydantic-ai` Agent with OpenAI-compatible Ollama provider (used by `RAGAgent`)
- **Active Issue**: Model output not being captured from `pydantic-ai` events in `track_tool_calls` function

## Migration Steps

### Step 1: Add OpenAI Dependency
**File**: `pyproject.toml`
- Verify `pydantic-ai>=0.0.12` is in dependencies (already present)
- `openai` package will be installed automatically via pydantic-ai
- Remove `ollama>=0.1.0` dependency (optional, can keep for now)

### Step 2: Update Configuration
**File**: `config/__init__.py`
- Add `OPENAI_API_KEY` environment variable
- Add `OPENAI_RAG_MODEL` and `OPENAI_JUDGE_MODEL` defaults
- Update `ModelType` enum to include OpenAI models (gpt-4o-mini, gpt-3.5-turbo, etc.)
- Remove or deprecate `OLLAMA_*` config variables
- Remove `ollama_client` initialization

### Step 3: Create OpenAILLM Class
**File**: `prompt/llm_utils.py`
- Create `OpenAILLM` class to replace `OllamaLLM`
- Use `pydantic-ai` instead of OpenAI SDK directly
- Use `OpenAIChatModel` with `OpenAIProvider` from `pydantic_ai`
- Create a simple `Agent` without tools for text generation
- Implement `query()` method that calls `agent.run()` and extracts text
- Update imports to use `pydantic_ai` instead of `ollama`

### Step 4: Update TextRAG
**File**: `source/text_rag.py`
- Replace `OllamaLLM` with `OpenAILLM`
- Update `RAGConfig` to use OpenAI model names
- Update initialization to use OpenAI config

### Step 5: Update RAG Agent
**File**: `rag_agent/agent.py`
- Replace Ollama provider with OpenAI provider
- Use `OpenAIProvider` from `pydantic_ai.providers.openai` (no base_url needed)
- Use `OpenAIChatModel` with OpenAI model names (gpt-4o-mini, gpt-3.5-turbo, etc.)
- Remove Ollama-specific code

### Step 6: Fix Model Output Capture
**File**: `rag_agent/agent.py` (track_tool_calls function)
- Add print statements to debug event handling
- Verify all event types are being received
- Check if OpenAI events differ from Ollama events
- Improve text extraction from `PartDeltaEvent`
- Add logging for `FinalResultEvent` to capture output
- Test with OpenAI to see if event structure is different

### Step 7: Update RAGConfig
**File**: `source/text_rag.py`
- Update `RAGConfig` dataclass to use OpenAI model names
- Change default from `OLLAMA_RAG_MODEL` to `OPENAI_RAG_MODEL`

### Step 8: Update Documentation
**Files**: `README.md`, `docker-compose.yml`
- Remove Ollama setup instructions
- Add OpenAI API key setup instructions
- Update environment variable examples
- Remove Ollama service comments from docker-compose.yml

### Step 9: Testing
- Test simple query with `TextRAG` using OpenAI
- Test agent query with `RAGAgent` using OpenAI
- Verify model output capture works with OpenAI
- Check that event streaming works correctly

## Model Output Capture Issue

### Current Problem
The `track_tool_calls` function in `rag_agent/agent.py` is not capturing model output text from `pydantic-ai` events. This is preventing debugging of validation failures.

### Debugging Strategy
1. **Add Print Statements**: Add `print()` statements alongside `logger.debug()` to see if events are being received
2. **Check Event Types**: Verify which event types are actually being emitted by OpenAI
3. **Inspect Event Structure**: Print full event structure to understand data format
4. **Test with OpenAI**: OpenAI events might have different structure than Ollama events
5. **Check FinalResultEvent**: Ensure we're capturing output from final result event

### Key Files to Modify
- `rag_agent/agent.py` - `track_tool_calls()` function (lines 31-141)
- `rag_agent/agent.py` - Exception handling (lines 229-358)

## Environment Variables Needed

Add to `.env`:
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_RAG_MODEL=gpt-4o-mini  # or gpt-3.5-turbo for cost efficiency
OPENAI_JUDGE_MODEL=gpt-4o-mini  # for future judge agent
```

## Default Model Recommendations

- **RAG Agent**: `gpt-4o-mini` (good balance of cost and quality, supports tools)
- **Text RAG**: `gpt-3.5-turbo` (cheaper for simple queries, no tools needed)
- **Judge Agent** (future): `gpt-4o-mini` or `gpt-4o` (for better reasoning)

## Testing Checklist

- [ ] OpenAI API key is set in environment
- [ ] Simple query works with TextRAG
- [ ] Agent query works with RAGAgent
- [ ] Tool calls are being tracked
- [ ] Model output is being captured in events
- [ ] Validation errors show captured output for debugging
- [ ] All CLI commands work with OpenAI

## Notes

- **Using pydantic-ai throughout**: Both TextRAG and RAGAgent will use pydantic-ai for consistency
- **TextRAG**: Will use pydantic-ai Agent without tools for simple text generation
- **RAGAgent**: Already uses pydantic-ai, just switching from Ollama to OpenAI provider
- **Consistency**: Both components use the same framework, making maintenance easier
- OpenAI models support tools natively, so no compatibility issues
- pydantic-ai has native OpenAI support, so migration should be straightforward
- Event structure might be more reliable with OpenAI than with Ollama
- Cost considerations: gpt-4o-mini is ~$0.15/$0.60 per 1M tokens (input/output)
- Rate limits: OpenAI has rate limits, but should be fine for development/testing
