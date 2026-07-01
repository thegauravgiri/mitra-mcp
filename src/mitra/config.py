import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_DIR = Path.home() / ".config" / "mitra"
CONFIG_FILE = CONFIG_DIR / "config.json"

import contextvars

# ContextVars to handle request-specific configurations in multi-user remote setups
request_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_api_key", default=None)
request_workspace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_workspace_id", default=None)
request_project_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_project_id", default=None)
request_wakatime_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_wakatime_api_key", default=None)


def get_config_dir() -> Path:
    """Returns the config directory and ensures it exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR

def load_config() -> Dict[str, Any]:
    """Loads the config file. Returns an empty dict if it doesn't exist."""
    get_config_dir()
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(config: Dict[str, Any]) -> None:
    """Saves the config dict to the config file."""
    get_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_clockify_api_key() -> Optional[str]:
    """Retrieves the Clockify API key from context, environment variables, or config file."""
    # Priority 1: Request context (for multi-user remote server via HTTP headers)
    api_key = request_api_key.get()
    if api_key:
        return api_key

    # Priority 2: Environment variable
    api_key = os.environ.get("CLOCKIFY_API_KEY")
    if api_key:
        return api_key
    
    # Priority 3: Config file
    config = load_config()
    return config.get("CLOCKIFY_API_KEY")

def get_workspace_id() -> Optional[str]:
    """Retrieves the default workspace ID from context, environment, or config."""
    # Priority 1: Request context
    ws_id = request_workspace_id.get()
    if ws_id:
        return ws_id

    # Priority 2: Environment variable
    ws_id = os.environ.get("CLOCKIFY_WORKSPACE_ID")
    if ws_id:
        return ws_id
    config = load_config()
    return config.get("CLOCKIFY_WORKSPACE_ID")

def get_project_id() -> Optional[str]:
    """Retrieves the default project ID from context, environment, or config."""
    # Priority 1: Request context
    proj_id = request_project_id.get()
    if proj_id:
        return proj_id

    # Priority 2: Environment variable
    proj_id = os.environ.get("CLOCKIFY_PROJECT_ID")
    if proj_id:
        return proj_id
    config = load_config()
    return config.get("CLOCKIFY_PROJECT_ID")
