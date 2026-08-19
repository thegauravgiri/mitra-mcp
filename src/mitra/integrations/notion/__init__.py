"""Notion integration for Mitra MCP Server.

Exposes the Notion Dashboard skill as an agent-discoverable prompt and resource.
"""

from mitra.integrations.notion.prompts import register_prompts


def register(mcp) -> None:
    """Register all Notion prompts and resources with the MCP server."""
    register_prompts(mcp)
