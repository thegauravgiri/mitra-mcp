"""WakaTime integration for Mitra MCP Server.

Provides tools for querying WakaTime coding activity summaries and file durations.
"""

from mitra.integrations.wakatime.tools import register_tools


def register(mcp) -> None:
    """Register all WakaTime tools with the MCP server."""
    register_tools(mcp)
