"""
Tests for the ServiceNow MCP server integration with catalog functionality.
"""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

import mcp.types as types

from servicenow_mcp.server import ServiceNowMCP

CATALOG_TOOLS = ["list_catalog_items", "get_catalog_item", "list_catalog_categories"]


class TestServerCatalog(unittest.TestCase):
    """Test cases for the server integration with catalog functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "instance_url": "https://example.service-now.com",
            "auth": {
                "type": "basic",
                "basic": {
                    "username": "admin",
                    "password": "password",
                },
            },
        }
        self.env_patcher = patch.dict(os.environ, {"MCP_TOOL_PACKAGE": "full"})
        self.env_patcher.start()
        self.server = ServiceNowMCP(self.config)

    def tearDown(self):
        self.env_patcher.stop()

    def test_catalog_tools_registered(self):
        """Catalog tools are defined and advertised by list_tools."""
        listed = {tool.name for tool in asyncio.run(self.server._list_tools_impl())}
        for tool in CATALOG_TOOLS:
            self.assertIn(tool, self.server.tool_definitions, f"{tool} missing from definitions")
            self.assertIn(tool, listed, f"{tool} not advertised by list_tools")

    def test_call_list_catalog_items_dispatches(self):
        """call_tool routes to the catalog implementation and serializes its result."""
        mock_impl = MagicMock(return_value={"items": [], "count": 0})
        definition = self.server.tool_definitions["list_catalog_items"]
        self.server.tool_definitions["list_catalog_items"] = (mock_impl,) + definition[1:]

        result = asyncio.run(self.server._call_tool_impl("list_catalog_items", {}))

        mock_impl.assert_called_once()
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], types.TextContent)
        self.assertIn("count", result[0].text)

    def test_call_unknown_tool_raises(self):
        """Calling a tool that does not exist raises a ValueError."""
        with self.assertRaises(ValueError):
            asyncio.run(self.server._call_tool_impl("nonexistent_tool", {}))


if __name__ == "__main__":
    unittest.main()
