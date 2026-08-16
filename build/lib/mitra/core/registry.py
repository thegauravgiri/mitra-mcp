"""Auto-discovery engine for Mitra integrations.

Scans the `integrations/` package for submodules that expose a `register(mcp)` function
and collects HTTP header mappings from each integration's `context` module.

This means:
- Adding a new integration = creating a folder under integrations/ with __init__.py
- Removing an integration = deleting that folder
- No other files need to be modified.
"""

import importlib
import logging
import pkgutil
from typing import Dict, List, Tuple, Callable

import contextvars

logger = logging.getLogger("mitra.core.registry")


def discover_integrations() -> List[str]:
    """Discover all integration subpackages under mitra.integrations.

    Returns:
        A list of fully qualified module names (e.g., ['mitra.integrations.clockify', ...]).
    """
    import mitra.integrations as integrations_pkg

    modules = []
    for importer, modname, ispkg in pkgutil.iter_modules(
        integrations_pkg.__path__, prefix=integrations_pkg.__name__ + "."
    ):
        if ispkg:
            modules.append(modname)
    return sorted(modules)


def register_all(mcp) -> None:
    """Discover and register all integrations with the MCP server.

    Each integration subpackage must have an `__init__.py` with a `register(mcp)` function.

    Args:
        mcp: The FastMCP server instance.
    """
    for module_name in discover_integrations():
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "register"):
                module.register(mcp)
                logger.info(f"Registered integration: {module_name}")
            else:
                logger.warning(
                    f"Integration {module_name} has no register(mcp) function — skipping."
                )
        except Exception:
            logger.exception(f"Failed to register integration: {module_name}")


def collect_headers() -> Dict[str, "contextvars.ContextVar"]:
    """Collect all HTTP header → ContextVar mappings from every integration.

    Each integration's `context` module may expose a `HEADERS` dict mapping
    HTTP header names (lowercase) to ContextVar instances.

    Returns:
        A merged dict of {header_name: context_var} across all integrations.
    """
    all_headers: Dict[str, contextvars.ContextVar] = {}

    # Include core headers (e.g. x-user-id)
    try:
        from mitra.core.user import HEADERS as core_headers
        all_headers.update(core_headers)
    except ImportError:
        pass

    for module_name in discover_integrations():
        context_module_name = f"{module_name}.context"
        try:
            context_module = importlib.import_module(context_module_name)
            if hasattr(context_module, "HEADERS"):
                headers = context_module.HEADERS
                all_headers.update(headers)
                logger.debug(
                    f"Collected {len(headers)} header(s) from {context_module_name}"
                )
        except ImportError:
            # Integration has no context module — that's fine (e.g., workflows)
            pass
        except Exception:
            logger.exception(
                f"Failed to collect headers from {context_module_name}"
            )

    return all_headers
