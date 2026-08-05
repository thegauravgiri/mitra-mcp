import os
import logging

try:
    from fastmcp import FastMCP
    IS_STANDALONE_FASTMCP = True
except ImportError:
    from mcp.server.fastmcp import FastMCP
    IS_STANDALONE_FASTMCP = False

try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:
    TransportSecuritySettings = None

from mitra.core.registry import register_all

logger = logging.getLogger("mitra.server")

# If ALLOWED_HOSTS is defined, delegate host check to the parent FastAPI app's
# TrustedHostMiddleware to avoid duplicate checks and 421 host errors.
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
if allowed_hosts_env and TransportSecuritySettings is not None and not IS_STANDALONE_FASTMCP:
    security_settings = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    security_settings = None

if security_settings is not None:
    mcp = FastMCP("Mitra", transport_security=security_settings)
else:
    mcp = FastMCP("Mitra")

# Auto-discover and register all integrations from mitra/integrations/
register_all(mcp)