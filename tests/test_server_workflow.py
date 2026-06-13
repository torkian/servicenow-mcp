"""
Tests for the ServiceNow MCP server workflow management integration.
"""

import asyncio
import os
import unittest
from unittest.mock import patch

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

WORKFLOW_TOOLS = [
    "list_workflows",
    "get_workflow_details",
    "list_workflow_versions",
    "get_workflow_activities",
    "create_workflow",
    "update_workflow",
    "activate_workflow",
    "deactivate_workflow",
    "add_workflow_activity",
    "update_workflow_activity",
    "delete_workflow_activity",
    "reorder_workflow_activities",
]


class TestServerWorkflow(unittest.TestCase):
    """Tests for the ServiceNow MCP server workflow management integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        # Load the full package so every workflow tool is enabled.
        self.env_patcher = patch.dict(os.environ, {"MCP_TOOL_PACKAGE": "full"})
        self.env_patcher.start()
        self.server = ServiceNowMCP(self.server_config)

    def tearDown(self):
        """Tear down test fixtures."""
        self.env_patcher.stop()

    def test_workflow_tools_registered(self):
        """Every workflow tool is defined and advertised by list_tools."""
        listed = {tool.name for tool in asyncio.run(self.server._list_tools_impl())}
        for tool in WORKFLOW_TOOLS:
            self.assertIn(tool, self.server.tool_definitions, f"{tool} missing from definitions")
            self.assertIn(tool, listed, f"{tool} not advertised by list_tools")

    def test_call_disabled_tool_raises(self):
        """Calling a tool that is not enabled raises a ValueError."""
        self.server.enabled_tool_names = [
            name for name in self.server.enabled_tool_names if name != "list_workflows"
        ]
        with self.assertRaises(ValueError):
            asyncio.run(self.server._call_tool_impl("list_workflows", {}))


if __name__ == "__main__":
    unittest.main()
