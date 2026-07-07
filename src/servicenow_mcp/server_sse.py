"""
ServiceNow MCP Server

This module provides the main implementation of the ServiceNow MCP server.
"""

import argparse
import asyncio
import logging
import os
from contextlib import suppress
from typing import Dict, Union

import uvicorn
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


logger = logging.getLogger(__name__)


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def sse_app(scope, receive, send) -> None:
        if scope.get("type") != "http":
            return

        if scope.get("method") != "GET":
            response = PlainTextResponse("Method Not Allowed", status_code=405)
            await response(scope, receive, send)
            return

        response_started = False

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") in {"http.response.start", "http.response.body"}:
                response_started = True
            await send(message)

        try:
            async with sse.connect_sse(
                scope,
                receive,
                tracked_send,
            ) as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except asyncio.CancelledError:
            # Expected during process shutdown with active SSE clients.
            logger.info("SSE connection cancelled during shutdown.")
            if response_started:
                # Ensure ASGI response is marked complete to avoid runtime noise.
                with suppress(Exception):
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

    return Starlette(
        debug=debug,
        routes=[
            Mount("/sse", app=sse_app),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


class ServiceNowSSEMCP(ServiceNowMCP):
    """
    ServiceNow MCP Server implementation.

    This class provides a Model Context Protocol (MCP) server for ServiceNow,
    allowing LLMs to interact with ServiceNow data and functionality.
    """

    def __init__(self, config: Union[Dict, ServerConfig]):
        """
        Initialize the ServiceNow MCP server.

        Args:
            config: Server configuration, either as a dictionary or ServerConfig object.
        """
        super().__init__(config)

    def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        keep_alive_timeout: int = 2,
        graceful_shutdown_timeout: int = 2,
    ):
        """
        Start the MCP server with SSE transport using Starlette and Uvicorn.

        Args:
            host: Host address to bind to
            port: Port to listen on
            keep_alive_timeout: Seconds to keep idle HTTP connections open
            graceful_shutdown_timeout: Seconds to wait before force-closing during shutdown
        """
        # Create Starlette app with SSE transport
        starlette_app = create_starlette_app(self.mcp_server, debug=False)

        # Run using uvicorn
        uvicorn.run(
            starlette_app,
            host=host,
            port=port,
            timeout_keep_alive=keep_alive_timeout,
            timeout_graceful_shutdown=graceful_shutdown_timeout,
        )


def create_servicenow_mcp(instance_url: str, username: str, password: str):
    """
    Create a ServiceNow MCP server with minimal configuration.

    This is a simplified factory function that creates a pre-configured
    ServiceNow MCP server with basic authentication.

    Args:
        instance_url: ServiceNow instance URL
        username: ServiceNow username
        password: ServiceNow password

    Returns:
        A configured ServiceNowMCP instance ready to use

    Example:
        ```python
        from servicenow_mcp.server import create_servicenow_mcp

        # Create an MCP server for ServiceNow
        mcp = create_servicenow_mcp(
            instance_url="https://instance.service-now.com",
            username="admin",
            password="password"
        )

        # Start the server
        mcp.start()
        ```
    """

    # Create basic auth config
    auth_config = AuthConfig(
        type=AuthType.BASIC, basic=BasicAuthConfig(username=username, password=password)
    )

    # Create server config
    config = ServerConfig(instance_url=instance_url, auth=auth_config)

    # Create and return server
    return ServiceNowSSEMCP(config)


def main():
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run ServiceNow MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument(
        "--keep-alive-timeout",
        type=int,
        default=2,
        help="Seconds to keep idle HTTP connections open (default: 2)",
    )
    parser.add_argument(
        "--graceful-shutdown-timeout",
        type=int,
        default=2,
        help="Seconds to wait before force-closing connections on shutdown (default: 2)",
    )
    args = parser.parse_args()

    server = create_servicenow_mcp(
        instance_url=os.getenv("SERVICENOW_INSTANCE_URL"),
        username=os.getenv("SERVICENOW_USERNAME"),
        password=os.getenv("SERVICENOW_PASSWORD"),
    )
    server.start(
        host=args.host,
        port=args.port,
        keep_alive_timeout=args.keep_alive_timeout,
        graceful_shutdown_timeout=args.graceful_shutdown_timeout,
    )


if __name__ == "__main__":
    main()
