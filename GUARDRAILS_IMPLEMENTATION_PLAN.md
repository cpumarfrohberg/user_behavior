# Guardrails Integration Plan for User Behavior Project

## Overview
Add real-time guardrail monitoring to the user_behavior project, allowing parallel execution of safety checks that can interrupt agent execution when violations are detected. This follows the pattern from the guardrails notebook work.

## Architecture

### Core Components to Add

1. **Guardrail Infrastructure Module** (`guardrails/__init__.py`)
   - `GuardrailException` class (custom exception for guardrail failures)
   - `GuardrailFunctionOutput` dataclass (output structure for guardrails)
   - `run_with_guardrails()` function (main orchestration function)

2. **Guardrail Implementations** (`guardrails/checks.py`)
   - Input validation guardrails (prohibited topics, content filtering)
   - Cost control guardrails (token limits, execution time)
   - Output quality guardrails (response validation)

3. **Configuration** (`guardrails/config.py`)
   - Guardrail configuration classes
   - Enable/disable flags per guardrail type

## Implementation Steps

### Step 1: Create Guardrails Module Structure

**Files to create:**
- `guardrails/__init__.py` - Main guardrail infrastructure
- `guardrails/checks.py` - Guardrail check implementations
- `guardrails/config.py` - Configuration classes

**Key code from guardrails notebook:**
```python
# guardrails/__init__.py
from dataclasses import dataclass
import asyncio

@dataclass
class GuardrailFunctionOutput:
    output_info: str
    tripwire_triggered: bool

class GuardrailException(Exception):
    def __init__(self, message: str, info: GuardrailFunctionOutput):
        super().__init__(message)
        self.info = info

async def run_with_guardrails(agent_coroutine, guardrails):
    """
    Run `agent_coroutine` while multiple guardrails monitor it.

    Parameters:
        agent_coroutine: an *awaitable*, e.g. agent()
        guardrails: an iterable of *awaitables*, e.g. [guard1(), guard2()]

    Returns:
        The result of the agent, if no guardrail triggers.

    Raises:
        GuardrailException from any guardrail.
    """
    agent_task = asyncio.create_task(agent_coroutine)
    guard_tasks = [asyncio.create_task(g) for g in guardrails]

    try:
        # If any guardrail raises GuardrailException, gather will throw and we drop into except.
        await asyncio.gather(agent_task, *guard_tasks)

        # Agent finished successfully.
        return agent_task.result()

    except GuardrailException as e:
        # At least one guardrail fired.
        print("[guardrail fired]", e.info)

        # Cancel the agent.
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            print("[run_with_guardrails] agent cancelled")

        # Cancel all guardrails (they may still be running).
        for t in guard_tasks:
            t.cancel()
        await asyncio.gather(*guard_tasks, return_exceptions=True)

        raise
```

### Step 2: Integrate into MongoDB Agent

**File to modify:** `mongodb_agent/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `MongoDBSearchAgent.__init__()`
- Wrap `self.agent.run()` call in `run_with_guardrails()` in `query()` method
- Update method signature: `async def query(self, question: str, guardrails: list = None) -> SearchAgentResult`

**Integration point:**
```python
# In query() method, replace:
result = await self.agent.run(question, event_stream_handler=track_tool_calls)

# With:
agent_coroutine = self.agent.run(question, event_stream_handler=track_tool_calls)
if guardrails:
    result = await run_with_guardrails(agent_coroutine, guardrails)
else:
    result = await agent_coroutine
```

### Step 3: Integrate into Orchestrator Agent

**File to modify:** `orchestrator/agent.py`

**Changes:**
- Add optional `guardrails` parameter to `OrchestratorAgent.__init__()`
- Wrap `self.agent.run()` call in `run_with_guardrails()` in `query()` method
- Update method signature: `async def query(self, question: str, guardrails: list = None) -> OrchestratorAnswer`

**Integration point:**
```python
# In query() method, replace:
result = await self.agent.run(question)

# With:
agent_coroutine = self.agent.run(question)
if guardrails:
    result = await run_with_guardrails(agent_coroutine, guardrails)
else:
    result = await agent_coroutine
```

### Step 4: Create Guardrail Check Functions

**File:** `guardrails/checks.py`

**Implementations:**
1. **Input validation guardrail:**
   ```python
   async def input_validation_guardrail(question: str, prohibited_topics: list[str] = None):
       """
       Check for prohibited topics in user input.

       Args:
           question: The user's question
           prohibited_topics: List of prohibited topic keywords

       Raises:
           GuardrailException if prohibited topic found
       """
       from guardrails import GuardrailException, GuardrailFunctionOutput

       if prohibited_topics is None:
           prohibited_topics = []

       question_lower = question.lower()
       for topic in prohibited_topics:
           if topic.lower() in question_lower:
               info = GuardrailFunctionOutput(
                   output_info=f'Input contains prohibited topic: {topic}',
                   tripwire_triggered=True
               )
               raise GuardrailException(f"Prohibited topic detected: {topic}", info)

       # Guardrail passes
       await asyncio.sleep(0.1)  # Allow other guardrails to run
   ```

2. **Cost control guardrail:**
   ```python
   async def cost_control_guardrail(agent_task, max_tokens: int = None, max_time: float = None):
       """
       Monitor token usage or execution time.

       Args:
           agent_task: The agent task being monitored
           max_tokens: Maximum tokens allowed (if tracking available)
           max_time: Maximum execution time in seconds

       Raises:
           GuardrailException if limits exceeded
       """
       from guardrails import GuardrailException, GuardrailFunctionOutput
       import time

       start_time = time.time()

       while not agent_task.done():
           await asyncio.sleep(0.5)  # Check every 500ms

           # Check time limit
           if max_time and (time.time() - start_time) > max_time:
               info = GuardrailFunctionOutput(
                   output_info=f'Execution time exceeded {max_time}s',
                   tripwire_triggered=True
               )
               raise GuardrailException(f"Execution time limit exceeded", info)

       # Guardrail passes
   ```

3. **Output quality guardrail:**
   ```python
   async def output_quality_guardrail(agent_task, min_confidence: float = None):
       """
       Validate output quality after agent completes.

       Args:
           agent_task: The agent task being monitored
           min_confidence: Minimum confidence threshold

       Raises:
           GuardrailException if quality too low
       """
       from guardrails import GuardrailException, GuardrailFunctionOutput

       # Wait for agent to complete
       try:
           result = await agent_task
           output = result.output

           # Check confidence if available
           if min_confidence and hasattr(output, 'confidence'):
               if output.confidence < min_confidence:
                   info = GuardrailFunctionOutput(
                       output_info=f'Output confidence {output.confidence} below threshold {min_confidence}',
                       tripwire_triggered=True
                   )
                   raise GuardrailException("Output quality too low", info)
       except asyncio.CancelledError:
           # Agent was cancelled, guardrail should not trigger
           pass
   ```

### Step 5: Update CLI to Support Guardrails

**File to modify:** `cli.py`

**Changes:**
- Add `--guardrails` flag to `agent_ask` and `orchestrator_ask` commands
- Create helper function to build guardrail list from config
- Pass guardrails to agent query methods

**Example:**
```python
from guardrails.checks import input_validation_guardrail
from guardrails import run_with_guardrails

@app.command()
def agent_ask(
    question: str,
    verbose: bool = False,
    enable_guardrails: bool = typer.Option(False, "--guardrails", help="Enable guardrails"),
):
    """Ask a question using the MongoDB agent directly (makes multiple searches)"""
    try:
        agent = _init_mongodb_agent(verbose)
        typer.echo(
            "🤖 Running agent query"
            + ("..." if verbose else " (this may take a minute)...")
        )

        async def run_query():
            guardrails = []
            if enable_guardrails:
                # Add input validation guardrail
                guardrails.append(input_validation_guardrail(question, prohibited_topics=["spam", "offensive"]))

            result = await agent.query(question, guardrails=guardrails)
            _print_answer(result, question, verbose)

        _run_async(run_query, verbose)
    except Exception as e:
        _handle_error(e, verbose)
```

### Step 6: Update Configuration

**File to modify:** `mongodb_agent/config.py` and `orchestrator/config.py`

**Changes:**
- Add `GuardrailConfig` dataclass with enable flags
- Add guardrail settings to agent configs

**Example:**
```python
# guardrails/config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class GuardrailConfig:
    """Configuration for guardrails"""
    enable_input_validation: bool = False
    prohibited_topics: list[str] = None
    enable_cost_control: bool = False
    max_tokens: Optional[int] = None
    max_time_seconds: Optional[float] = None
    enable_output_quality: bool = False
    min_confidence: Optional[float] = None

    def __post_init__(self):
        if self.prohibited_topics is None:
            self.prohibited_topics = []
```

### Step 7: Update Tests

**Files to modify:**
- `tests/mongodb_agent/test_agent.py` - Add tests for guardrail integration
- Create `tests/orchestrator/test_agent.py` if it doesn't exist - Add guardrail tests

**Test cases:**
- Agent runs successfully without guardrails
- Agent is cancelled when guardrail triggers
- Multiple guardrails can run in parallel
- GuardrailException is properly raised and handled

**Example test:**
```python
async def test_agent_with_guardrail_cancellation(initialized_agent):
    """Test that agent is cancelled when guardrail triggers"""
    from guardrails import GuardrailException
    from guardrails.checks import input_validation_guardrail

    question = "This contains spam content"
    guardrails = [input_validation_guardrail(question, prohibited_topics=["spam"])]

    with pytest.raises(GuardrailException):
        await initialized_agent.query(question, guardrails=guardrails)
```

### Step 8: Documentation

**File to create:** `guardrails/README.md`

**Content:**
- How guardrails work
- How to create custom guardrails
- Configuration options
- Examples

## Files to Create

1. `guardrails/__init__.py` - Core infrastructure
2. `guardrails/checks.py` - Guardrail implementations
3. `guardrails/config.py` - Configuration
4. `guardrails/README.md` - Documentation

## Files to Modify

1. `mongodb_agent/agent.py` - Add guardrail support
2. `orchestrator/agent.py` - Add guardrail support
3. `cli.py` - Add CLI flags for guardrails
4. `mongodb_agent/config.py` - Add guardrail config (optional)
5. `orchestrator/config.py` - Add guardrail config (optional)
6. `tests/mongodb_agent/test_agent.py` - Add guardrail tests

## Backward Compatibility

- All guardrail parameters are optional (default to `None` or empty list)
- Existing code continues to work without changes
- Guardrails are opt-in via configuration or CLI flags
- No breaking changes to existing API

## Testing Strategy

1. Unit tests for guardrail infrastructure
2. Integration tests for agent + guardrail interaction
3. Test guardrail cancellation behavior
4. Test multiple guardrails running in parallel
5. Test that agent results are correct when guardrails pass

## Configuration Example

```python
# In agent config
from guardrails.config import GuardrailConfig

guardrails_config = GuardrailConfig(
    enable_input_validation=True,
    prohibited_topics=["spam", "offensive"],
    enable_cost_control=True,
    max_tokens=10000,
    max_time_seconds=60.0,
    enable_output_quality=True,
    min_confidence=0.7
)
```

## Integration Points Summary

- **MongoDB Agent**: `mongodb_agent/agent.py:169` - Wrap `self.agent.run()` call
- **Orchestrator Agent**: `orchestrator/agent.py:75` - Wrap `self.agent.run()` call
- **CLI**: `cli.py:100` and `cli.py:136` - Pass guardrails to query methods
- **Evaluation**: `evals/evaluate.py:95` - Guardrails can be passed through `agent_query_fn`

## Implementation Order

1. Create guardrails module structure (`guardrails/__init__.py`)
2. Implement guardrail check functions (`guardrails/checks.py`)
3. Add guardrail configuration (`guardrails/config.py`)
4. Integrate into MongoDB agent
5. Integrate into Orchestrator agent
6. Update CLI to support guardrails
7. Add tests
8. Create documentation

## Notes

- Guardrails run in parallel with the agent using `asyncio.gather()`
- When a guardrail triggers, it raises `GuardrailException` which cancels the agent task
- Multiple guardrails can monitor the same agent execution
- Guardrails are async functions that can perform checks at any time during execution
- The pattern follows the guardrails notebook implementation from week4 notes
