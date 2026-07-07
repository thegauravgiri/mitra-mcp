"""Cross-integration workflows for Mitra MCP Server.

Provides composite tools that span multiple integrations:
- Clockify ↔ Azure DevOps linkage (log time for a card)
- Fill-clockify (gather WakaTime + Clockify + Azure DevOps data in one call)
- Unified agent guide prompt
"""

from mitra.integrations.workflows.linkage import register_tools as register_linkage_tools
from mitra.integrations.workflows.fill_clockify import register_tools as register_fill_tools
from mitra.integrations.workflows.prompts import register_prompts


def register(mcp) -> None:
    """Register all cross-integration workflow tools, prompts, and resources."""
    register_linkage_tools(mcp)
    register_fill_tools(mcp)
    register_prompts(mcp)
