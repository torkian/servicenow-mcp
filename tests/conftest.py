"""Pytest configuration: patch broken mcp import for tests."""
import sys
from unittest.mock import MagicMock

# mcp 1.3.0 has a bug with pydantic >= 2.9 (eval_type_backport removed).
# Patch the mcp module and all sub-modules before servicenow_mcp.__init__ imports.
def _make_mcp_mocks():
    mcp_mock = MagicMock()
    submodules = [
        "mcp",
        "mcp.types",
        "mcp.server",
        "mcp.server.fastmcp",
        "mcp.server.fastmcp.server",
        "mcp.server.fastmcp.tools",
        "mcp.server.fastmcp.utilities",
        "mcp.server.fastmcp.utilities.func_metadata",
        "mcp.server.lowlevel",
        "mcp.server.session",
        "mcp.server.stdio",
        "mcp.server.sse",
    ]
    for mod in submodules:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

_make_mcp_mocks()
