from mcp.server.fastmcp import FastMCP
import logging

from mitra.core.registry import register_all

logger = logging.getLogger("mitra.server")

mcp = FastMCP("Mitra")

# Auto-discover and register all integrations from mitra/integrations/
register_all(mcp)