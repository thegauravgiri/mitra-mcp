"""Azure DevOps integration for Mitra MCP Server.

Provides tools for managing Azure DevOps work items (cards), projects, and queries.
"""

from mitra.integrations.azure_devops.tools import register_tools
from mitra.integrations.azure_devops.prompts import register_prompts


def register(mcp) -> None:
    """Register all Azure DevOps tools, prompts, and resources with the MCP server."""
    register_tools(mcp)
    register_prompts(mcp)
