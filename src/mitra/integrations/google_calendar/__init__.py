"""Google Calendar integration for Mitra MCP Server.

Provides tools for fetching and managing calendar events, allowing coordination
with Clockify and workflows.
"""

from mitra.integrations.google_calendar.tools import register_tools


def register(mcp) -> None:
    """Register all Google Calendar tools with the MCP server."""
    register_tools(mcp)
