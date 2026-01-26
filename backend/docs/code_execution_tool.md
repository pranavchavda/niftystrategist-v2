# Code Execution Tool (Analysis Tool)

## Overview

The orchestrator now supports Anthropic's built-in **CodeExecutionTool** when running on Claude models. This enables the **Analysis Tool** feature, which allows Claude to execute Python code in a sandboxed environment during conversations.

## What is the Analysis Tool?

The Analysis Tool is Anthropic's feature that allows Claude to:
- Write and execute Python code to solve problems
- Perform calculations, data analysis, and transformations
- Work with uploaded files and context (e.g., "skills" uploaded to the API console)
- Generate visualizations and process structured data

## Implementation

### Backend Changes

1. **Base Agent (`base_agent.py`)**:
   - Added `builtin_tools` parameter to `__init__()` method
   - Passes builtin tools to Pydantic AI's `Agent` constructor

2. **Orchestrator (`orchestrator.py`)**:
   - Imports `CodeExecutionTool` from `pydantic_ai.builtin_tools`
   - Conditionally enables the tool for Claude models only
   - Logs when CodeExecutionTool is enabled

### Usage

When the orchestrator is initialized with a Claude model (e.g., `claude-haiku-4.5`), the CodeExecutionTool is automatically enabled:

```python
from agents.orchestrator import OrchestratorAgent

# CodeExecutionTool will be automatically enabled for Claude models
agent = OrchestratorAgent(
    model_id='claude-haiku-4.5',
    model_slug='claude-haiku-4-5-20251001',
    use_openrouter=False
)
```

### Logging

When enabled, you'll see this log message:
```
✓ Enabled CodeExecutionTool for Claude model (Analysis Tool with skills context)
```

## Benefits

1. **Enhanced Problem Solving**: Claude can execute code to verify calculations, test approaches, and solve complex problems
2. **Skills Context**: Any "skills" or context uploaded to the Anthropic API console can be used during code execution
3. **Data Processing**: Better handling of structured data, JSON parsing, and transformations
4. **Verification**: Claude can verify its own responses by running code

## Model Support

- ✅ **Claude models** (claude-haiku-4.5, claude-sonnet-4.5, etc.)
- ❌ **OpenRouter models** (not supported via OpenRouter)
- ❌ **OpenAI models** (different builtin tools)

## Security

The CodeExecutionTool runs in a sandboxed environment provided by Anthropic, ensuring safe execution without access to the system.

## Example Use Cases

1. **Complex Calculations**: "Calculate the compound interest on $10,000 at 5% APR for 10 years with monthly compounding"
2. **Data Analysis**: "Analyze this sales data and show me the top 5 products by revenue"
3. **Code Verification**: "Write a function to validate email addresses and test it with these examples"
4. **JSON Parsing**: "Parse this complex JSON structure and extract the nested values"

## Notes

- The tool is only enabled when running on Claude models via direct Anthropic API
- OpenRouter does not support builtin tools, so they're disabled when `use_openrouter=True`
- The feature requires Pydantic AI's `builtin_tools` parameter support
