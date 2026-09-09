"""Jira integration for Mitra MCP Server.

Provides tools for managing Jira issues, projects, comments, transitions, and links.
"""

from mitra.integrations.jira.tools import register_tools
from mitra.integrations.jira.prompts import register_prompts


def register(mcp) -> None:
    """Register all Jira tools, prompts, and resources with the MCP server."""
    register_tools(mcp)
    register_prompts(mcp)
