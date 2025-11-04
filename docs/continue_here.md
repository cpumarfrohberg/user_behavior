# Continue Here: Model Output Extraction Debugging

## Problem Statement

**Issue**: Model output is not being captured from pydantic-ai events, making it impossible to debug validation failures.

**Symptoms**:
- Validation error: "Exceeded maximum retries (1) for output validation"
- `_accumulated_text` is empty (no text captured)
- No debug logs appearing from event handler
- Tool calls work fine (FunctionToolCallEvent is received)

## Current Status

### What's Working ✅
- Tool calls execute successfully (2 searches completed)
- Event handler is registered and called for tool calls
- Print statements work (tool calls are displayed)
- Debug logging works in other modules (`🔍 DEBUG:` appears)

### What's NOT Working ❌
- No text captured from model output (`_accumulated_text` is empty)
- No debug logs appearing from event handler:
  - Missing: `📨 Event received: ...` logs
  - Missing: `PartDeltaEvent received...` logs
  - Missing: Delta extraction logs

## Key Observations

1. **FunctionToolCallEvent works** - Tool calls are logged via `print()` statements
2. **PartDeltaEvent may not be received** - No debug logs for text events
3. **Debug logs from other modules work** - `🔍 DEBUG:` appears for document loading
4. **Event handler debug logs don't appear** - `logger.debug()` statements not visible

## Hypotheses

### Hypothesis 1: Logger Configuration Issue
**Theory**: The `rag_agent` logger may not be set to DEBUG level, even though `LOG_LEVEL=DEBUG` is set.

**Evidence**:
- Debug logs from other modules appear
- Event handler debug logs don't appear
- Print statements work

**Test**:
- Check logger configuration for `rag_agent` module
- Verify `LOG_LEVEL=DEBUG` is being applied to this logger
- Add `print()` statements alongside `logger.debug()` to confirm handler is called

### Hypothesis 2: Event Handler Not Receiving Text Events
**Theory**: `PartDeltaEvent` events may not be emitted or may be filtered out before reaching the handler.

**Evidence**:
- FunctionToolCallEvent works (handler is called)
- No PartDeltaEvent logs appear
- No text is accumulated

**Test**:
- Verify event handler registration: `event_stream_handler=track_tool_calls`
- Check pydantic-ai documentation for event handler usage
- Add `print()` statements in event handler to confirm it's being called for ALL events

### Hypothesis 3: Model Output Delivery Mechanism
**Theory**: Model output may be delivered via a different mechanism (e.g., only in FinalResultEvent, or in exception after validation fails).

**Evidence**:
- Validation fails before completion
- No delta events captured
- Exception might contain the output

**Test**:
- Check if FinalResultEvent contains output
- Verify exception extraction path in error handling
- Check pydantic-ai documentation for output delivery

### Hypothesis 4: Event Stream Filtering
**Theory**: Events may be filtered or routed differently, preventing text events from reaching handler.

**Evidence**:
- Tool call events work
- Text events don't appear

**Test**:
- Check if there are filters on the event stream
- Verify event handler is called for all event types
- Check pydantic-ai version and event system

## Next Steps

### Step 1: Add Print Statements (Quick Test)
**Priority**: HIGH
**Time**: 5 minutes

Add `print()` statements in event handler to confirm it's being called for ALL events:

```python
# At the start of track_tool_calls, after logging event type
print(f"🔍 EVENT HANDLER CALLED: {event_type}")
```

This will help determine if:
- It's a logger issue (print works but logger doesn't)
- Handler isn't being called for text events

### Step 2: Verify Logger Configuration
**Priority**: HIGH
**Time**: 10 minutes

Check if `rag_agent` logger is configured correctly:

1. Check where loggers are configured (likely in `config/__init__.py` or main entry point)
2. Verify `LOG_LEVEL=DEBUG` is being applied to `rag_agent` logger
3. Try explicitly setting logger level in `agent.py`:
   ```python
   logger.setLevel(logging.DEBUG)
   ```

### Step 3: Check Event Handler Registration
**Priority**: MEDIUM
**Time**: 10 minutes

Verify event handler is correctly registered:

1. Check `agent.run()` call in `query()` method
2. Verify `event_stream_handler=track_tool_calls` is passed correctly
3. Check pydantic-ai documentation for correct event handler usage
4. Look for any examples or tests in the codebase

### Step 4: Inspect Exception for Model Output
**Priority**: MEDIUM
**Time**: 15 minutes

The exception might contain the model output:

1. Check if exception has `last_assistant_message` attribute
2. Check if exception has `tool_retry.model_response()` that contains output
3. Verify the fallback extraction path in exception handling (lines 203-301)
4. Add more detailed logging in exception handler

### Step 5: Check pydantic-ai Event System
**Priority**: LOW
**Time**: 30 minutes

Research pydantic-ai event system:

1. Check pydantic-ai documentation for event types
2. Verify which events are emitted for streaming responses
3. Check if there's a different event type for model output
4. Look for examples or tests that capture model output

## Code Locations

### Event Handler
- File: `rag_agent/agent.py`
- Lines: 31-115
- Function: `track_tool_calls()`
- Current debug logging: Lines 42-43, 70-110

### Error Handling
- File: `rag_agent/agent.py`
- Lines: 203-301
- Function: `query()` exception handler
- Fallback extraction: Lines 207-264

### Agent Initialization
- File: `rag_agent/agent.py`
- Lines: 132-174
- Event handler registration: Line 201 (`event_stream_handler=track_tool_calls`)

## Files Modified

- `rag_agent/agent.py` - Cleaned up and enhanced with debug logging

## Key Questions to Answer

1. Why are `logger.debug()` statements not appearing while `print()` statements do?
2. Are `PartDeltaEvent` events being emitted at all?
3. Is the event handler being called for text/model output events?
4. Where is the model's actual output being stored if not in delta events?
5. Is the logger configuration preventing debug logs from appearing?

## Success Criteria

We'll know we've solved it when:
- ✅ Debug logs appear showing `PartDeltaEvent` received
- ✅ Text is accumulated across multiple delta events
- ✅ Model output is captured and can be inspected for validation errors
- ✅ We can see the full JSON/text that the model produced before validation failed
