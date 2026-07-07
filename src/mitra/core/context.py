"""Base context utilities shared across integrations.

Each integration defines its own context vars in its own context.py module.
This module provides common helpers used by all integrations.
"""

import os
import contextvars
from typing import Optional


def resolve_credential(
    context_var: contextvars.ContextVar[Optional[str]],
    env_var_name: str,
) -> Optional[str]:
    """Resolve a credential from a ContextVar (set via HTTP headers) or an environment variable.

    Priority order:
    1. ContextVar value (set by SSE middleware from HTTP headers)
    2. Environment variable (set in shell for stdio mode)

    Args:
        context_var: The ContextVar that may hold the value from an HTTP header.
        env_var_name: The name of the environment variable to fall back to.

    Returns:
        The resolved credential value, or None if not found anywhere.
    """
    return context_var.get() or os.environ.get(env_var_name)
