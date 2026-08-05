import os
import logging

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:
    TransportSecuritySettings = None

from mitra.core.registry import register_all

logger = logging.getLogger("mitra.server")

# If ALLOWED_HOSTS is defined, delegate host check to the parent FastAPI app's
# TrustedHostMiddleware to avoid duplicate checks and 421 host errors.
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
if allowed_hosts_env and TransportSecuritySettings is not None:
    security_settings = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    security_settings = None

mcp = FastMCP("Mitra", transport_security=security_settings) if security_settings else FastMCP("Mitra")

# Auto-discover and register all integrations from mitra/integrations/
register_all(mcp)