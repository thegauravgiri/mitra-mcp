"""Clockify integration for Mitra MCP Server.

Provides tools for managing Clockify time entries, timers, projects, and workspaces.
"""

from mitra.integrations.clockify.tools import register_tools
from mitra.integrations.clockify.prompts import register_prompts


def register(mcp) -> None:
    """Register all Clockify tools, prompts, and resources with the MCP server."""
    register_tools(mcp)
    register_prompts(mcp)
