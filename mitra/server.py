from mcp.server.fastmcp import FastMCP
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from mitra.config import get_clockify_api_key, get_workspace_id, get_project_id
from mitra.clockify import ClockifyClient
import mitra.git_utils as git
import mitra.timers as local_timers

logger = logging.getLogger("mitra.server")

mcp = FastMCP("Mitra")

def _resolve_api_key(api_key: Optional[str] = None) -> str:
    key = api_key or get_clockify_api_key()
    if not key:
        raise ValueError("Clockify API Key not found. Please set CLOCKIFY_API_KEY environment variable or configure it via the CLI.")
    return key

# --- Clockify Tools ---

@mcp.tool()
async def clockify_get_user_info(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Gets the authenticated Clockify user details, including ID and default workspace."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_current_user()

@mcp.tool()
async def clockify_list_workspaces(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all Clockify workspaces available to the user."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_workspaces()

@mcp.tool()
async def clockify_list_projects(workspace_id: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all projects for the specified Clockify workspace."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_projects(workspace_id)

@mcp.tool()
async def clockify_add_time_entry(
    workspace_id: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: str = "",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new time entry in Clockify.
    start_time and end_time must be in ISO 8601 UTC format (e.g., YYYY-MM-DDTHH:MM:SSZ).
    """
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.add_time_entry(
        workspace_id=workspace_id,
        start_time=start_time,
        end_time=end_time,
        description=description,
        project_id=project_id,
        task_id=task_id
    )

@mcp.tool()
async def clockify_get_running_timer(
    workspace_id: str,
    user_id: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Retrieves the currently running Clockify timer for the specified user and workspace."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_running_timer(workspace_id, user_id)

@mcp.tool()
async def clockify_stop_running_timer(
    workspace_id: str,
    user_id: str,
    end_time: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Stops the currently running Clockify timer for the specified user and workspace."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.stop_running_timer(workspace_id, user_id, end_time)

# --- Git Tools ---

@mcp.tool()
def git_get_status(repo_path: str) -> str:
    """Gets the git status output for a repository path (useful to identify changes)."""
    return git.get_git_status(repo_path)

@mcp.tool()
def git_get_diff(
    repo_path: str,
    file_path: Optional[str] = None,
    since: Optional[str] = None,
    cached: bool = False
) -> str:
    """
    Gets the git diff for a repository.
    Can be filtered by file path or since a specific commit/branch.
    Set cached=True to get staged changes only.
    """
    return git.get_git_diff(repo_path, file_path=file_path, since=since, cached=cached)

@mcp.tool()
def git_get_recent_commits(repo_path: str, count: int = 5) -> str:
    """Lists the latest commits in the repository (useful for summarizing done work)."""
    return git.get_recent_commits(repo_path, count=count)

# --- Local Activity Timer Tools ---

@mcp.tool()
def mitra_start_timer(
    file_path: str,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """Starts a local time tracking session for a specific file."""
    ws_id = workspace_id or get_workspace_id()
    proj_id = project_id or get_project_id()
    return local_timers.start_timer(file_path, workspace_id=ws_id, project_id=proj_id, description=description)

@mcp.tool()
def mitra_stop_timer(file_path: str) -> Dict[str, Any]:
    """Stops local tracking for a file and returns start time, end time, and total duration."""
    return local_timers.stop_timer(file_path)

@mcp.tool()
def mitra_list_timers() -> List[Dict[str, Any]]:
    """Lists all active local timers and their elapsed time in seconds."""
    return local_timers.get_active_timers()
