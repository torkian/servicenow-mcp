# Contributing to ServiceNow MCP Server

Thanks for your interest in contributing! This is an actively maintained project and we review PRs promptly.

## Quick Start

```bash
git clone https://github.com/torkian/servicenow-mcp.git
cd servicenow-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q
```

## Development Workflow

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write code + tests
4. Run checks:
   ```bash
   ruff check . --select E,F --ignore E501
   pytest tests/ -q --cov=servicenow_mcp
   ```
5. Push and open a PR

## Adding a New Tool

1. Create or edit a module in `src/servicenow_mcp/tools/`
2. Define a Pydantic params model
3. Implement the tool function with signature: `(auth_manager, server_config, params) -> Dict`
4. Register in `src/servicenow_mcp/tools/__init__.py`
5. Register in `src/servicenow_mcp/utils/tool_utils.py` inside `get_tool_definitions()`
6. Add to the appropriate packages in `config/tool_packages.yaml`
7. Write tests in `tests/`

## Test Patterns

We use `unittest` with `unittest.mock`. See `tests/test_sctask_tools.py` for a clean example:

- Mock `AuthManager` with `MagicMock(spec=AuthManager)`
- Patch `requests.get/post/patch` at the module level
- Test success, error, and edge cases
- Verify mock calls and return values

## Code Style

- Ruff for linting (E, F rules)
- Line length: 100
- Python 3.11+
- Type hints on function signatures

## What We Look For in PRs

- Tests for all new code
- Clean, focused changes (one feature per PR)
- Follows existing patterns
- No breaking changes to existing tools
- Coverage maintained at 80%+
