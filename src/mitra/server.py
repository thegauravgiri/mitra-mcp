import os
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import logging

from mitra.core.registry import register_all

logger = logging.getLogger("mitra.server")

# If ALLOWED_HOSTS is defined, delegate host check to the parent FastAPI app's
# TrustedHostMiddleware to avoid duplicate checks and 421 host errors.
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
if allowed_hosts_env:
    security_settings = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    security_settings = None

mcp = FastMCP("Mitra", transport_security=security_settings)

# Auto-discover and register all integrations from mitra/integrations/
register_all(mcp)