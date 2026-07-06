from mcp.server.fastmcp import FastMCP
import logging

from mitra.tools import register_all
from mitra.prompts.guides import register as register_prompts

logger = logging.getLogger("mitra.server")

mcp = FastMCP("Mitra")

# Register all tools from submodules
register_all(mcp)

# Register all prompts and resources
register_prompts(mcp)