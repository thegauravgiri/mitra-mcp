from mcp.server.fastmcp import FastMCP
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from mitra.config import get_clockify_api_key
from mitra.clockify import ClockifyClient

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
    billable: bool = True,
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
        task_id=task_id,
        billable=billable
    )

@mcp.tool()
async def clockify_get_time_entry(
    workspace_id: str,
    time_entry_id: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves a specific Clockify time entry by ID."""
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_time_entry(workspace_id, time_entry_id)

@mcp.tool()
async def clockify_update_time_entry(
    workspace_id: str,
    time_entry_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    billable: Optional[bool] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates an existing time entry in Clockify.
    Only the provided fields (like description, billable, project_id, task_id) will be updated.
    """
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.update_time_entry(
        workspace_id=workspace_id,
        time_entry_id=time_entry_id,
        start_time=start_time,
        end_time=end_time,
        description=description,
        project_id=project_id,
        task_id=task_id,
        billable=billable
    )

@mcp.tool()
async def clockify_get_time_entries(
    workspace_id: str,
    user_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    project_id: Optional[str] = None,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves a list of time entries for a user in a workspace.
    If user_id is not specified, it defaults to the authenticated user.
    Can be filtered by project_id and a date range (start_time and end_time).
    start_time and end_time must be in ISO 8601 UTC format (e.g., YYYY-MM-DDTHH:MM:SSZ).
    """
    client = ClockifyClient(_resolve_api_key(api_key))
    return await client.get_time_entries(
        workspace_id=workspace_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        project_id=project_id
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

# --- Prompts and Resources for AI Agents ---

CLOCKIFY_RULES_GUIDE = """# Clockify AI Agent Instructions & Rules

You are an AI Agent assisting the developer with project time-tracking. You run locally in the developer's VS Code environment and connect to the remote Mitra MCP Server. Follow this step-by-step checklist strictly to handle requests quickly, securely, and without ambiguity:

## STEP 1: Check if the request is an EXPLICIT time-logging request
- **Explicit Request**: If the user tells you to log a time entry with specific times/durations and description (e.g. "add this from 9 AM to 10 AM", "log 1.5 hours for fixing bugs"), **DO NOT run any local tools** (no git diff, no git status).
- **Action**: Immediately parse the requested times and description, resolve the Project ID (see STEP 4), and call `clockify_add_time_entry` directly. Do not waste time analyzing local workspace state.

## STEP 2: Fetch WakaTime Coding Activity locally
- WakaTime data must be fetched **locally by you (the client agent)** from the developer's machine:
  1. Read the developer's local `~/.wakatime.cfg` file to extract the WakaTime `api_key`.
  2. Perform a local HTTPS request or run a local `curl` command using the extracted API key to query the WakaTime API:
     `curl -u "<API_KEY>:" "https://wakatime.com/api/v1/users/current/summaries?start=<TODAY>&end=<TODAY>&project=<PROJECT_NAME>"`
  3. Parse the JSON response to extract files (`entities`) and their `total_seconds` of coding time.
  4. Use this local data to calculate durations and draft descriptions for Clockify.

## STEP 3: Check Git Changes for Context (Fallback only)
- Only if the description of work or list of edited files is not specified, run local git commands (like `git diff`, `git status`) to summarize the changes. Keep descriptions concise.

## STEP 4: Project ID Discovery & Caching
- **Do NOT assume** the project ID is predefined.
- **First-Time Discovery**: If the project ID is not in context/history, use `clockify_list_projects` to list workspace projects, ask the user to confirm/choose the project, and then store/cache that project-to-file/folder mapping in your session history.
- **Reuse Cache**: For all subsequent requests within the same project/session context, **reuse the cached project ID**. Do not ask the user again.

## STEP 5: Batch Logging for Multiple Items
- If multiple files have untracked time across projects:
  - **Consolidate & Batch**: List all identified entries, group them by their respective projects, and call `clockify_add_time_entry` sequentially for all remaining items in a single turn. Do not process them one-by-one in separate user prompts.
"""

@mcp.prompt()
def clockify_agent_guide() -> str:
    """Provides the rule guide for the AI Agent regarding Clockify logging and project discovery."""
    return CLOCKIFY_RULES_GUIDE

@mcp.resource("instructions://clockify-rules")
def clockify_rules_resource() -> str:
    """Read-only access to the Clockify tracking and logging rules guide for AI Agents."""
    return CLOCKIFY_RULES_GUIDE

