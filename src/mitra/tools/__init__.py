"""Tools package initialization to register all tools."""

def register_all(mcp) -> None:
    """Register all tools from various submodules."""
    from mitra.tools import clockify, wakatime, azure_devops, linkage
    
    clockify.register(mcp)
    wakatime.register(mcp)
    azure_devops.register(mcp)
    linkage.register(mcp)
