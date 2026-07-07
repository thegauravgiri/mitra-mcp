"""Clockify MCP tool registrations."""

from typing import Optional, List, Dict, Any

from mitra.integrations.clockify.client import ClockifyClient
from mitra.integrations.clockify.context import get_clockify_api_key, get_workspace_id


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    """Resolve Clockify API key from parameter, request context, or env."""
    key = api_key or get_clockify_api_key()
    if not key:
        raise ValueError(
            "Clockify API Key not found. Please provide the 'api_key' parameter, "
            "set it via client headers, or set CLOCKIFY_API_KEY environment variable."
        )
    return key


def _resolve_workspace_id(workspace_id: Optional[str] = None) -> str:
    """Resolve Clockify Workspace ID from parameter, request context, or env."""
    ws_id = workspace_id or get_workspace_id()
    if not ws_id:
        raise ValueError(
            "Clockify Workspace ID not found. Please provide the 'workspace_id' parameter, "
            "set it via client headers, or set CLOCKIFY_WORKSPACE_ID environment variable."
        )
    return ws_id


def register_tools(mcp) -> None:
    """Register all Clockify tools with the MCP server."""

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
    async def clockify_list_projects(workspace_id: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all projects for the specified Clockify workspace."""
        client = ClockifyClient(_resolve_api_key(api_key))
        return await client.get_projects(_resolve_workspace_id(workspace_id))

    @mcp.tool()
    async def clockify_add_time_entry(
        workspace_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: str = "",
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        billable: bool = True,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new time entry in Clockify.
        start_time and end_time must be in ISO 8601 UTC format (e.g., YYYY-MM-DDTHH:MM:SSZ).
        """
        import datetime
        client = ClockifyClient(_resolve_api_key(api_key))
        # Default start_time to now if not provided
        st_time = start_time or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return await client.add_time_entry(
            workspace_id=_resolve_workspace_id(workspace_id), start_time=st_time, end_time=end_time,
            description=description, project_id=project_id, task_id=task_id, billable=billable,
        )

    @mcp.tool()
    async def clockify_get_time_entry(
        time_entry_id: str, workspace_id: Optional[str] = None, api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves a specific Clockify time entry by ID."""
        client = ClockifyClient(_resolve_api_key(api_key))
        return await client.get_time_entry(_resolve_workspace_id(workspace_id), time_entry_id)

    @mcp.tool()
    async def clockify_update_time_entry(
        time_entry_id: str,
        workspace_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        billable: Optional[bool] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates an existing time entry in Clockify.
        Only the provided fields (like description, billable, project_id, task_id) will be updated.
        """
        client = ClockifyClient(_resolve_api_key(api_key))
        return await client.update_time_entry(
            workspace_id=_resolve_workspace_id(workspace_id), time_entry_id=time_entry_id,
            start_time=start_time, end_time=end_time, description=description,
            project_id=project_id, task_id=task_id, billable=billable,
        )

    @mcp.tool()
    async def clockify_get_time_entries(
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        project_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves a list of time entries for a user in a workspace.
        If user_id is not specified, it defaults to the authenticated user.
        Can be filtered by project_id and a date range (start_time and end_time).
        start_time and end_time must be in ISO 8601 UTC format (e.g., YYYY-MM-DDTHH:MM:SSZ).
        """
        client = ClockifyClient(_resolve_api_key(api_key))
        return await client.get_time_entries(
            workspace_id=_resolve_workspace_id(workspace_id), user_id=user_id,
            start_time=start_time, end_time=end_time, project_id=project_id,
        )

    @mcp.tool()
    async def clockify_get_running_timer(
        workspace_id: Optional[str] = None, user_id: Optional[str] = None, api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves the currently running Clockify timer for the specified user and workspace."""
        client = ClockifyClient(_resolve_api_key(api_key))

        # If user_id is not provided, fetch it using get_current_user
        resolved_user_id = user_id
        if not resolved_user_id:
            user = await client.get_current_user()
            resolved_user_id = user["id"]

        return await client.get_running_timer(_resolve_workspace_id(workspace_id), resolved_user_id)

    @mcp.tool()
    async def clockify_stop_running_timer(
        workspace_id: Optional[str] = None, user_id: Optional[str] = None, end_time: Optional[str] = None, api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Stops the currently running Clockify timer for the specified user and workspace."""
        client = ClockifyClient(_resolve_api_key(api_key))

        resolved_user_id = user_id
        if not resolved_user_id:
            user = await client.get_current_user()
            resolved_user_id = user["id"]

        return await client.stop_running_timer(_resolve_workspace_id(workspace_id), resolved_user_id, end_time)

    @mcp.tool()
    async def clockify_quick_status(
        workspace_id: Optional[str] = None, api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns a complete Clockify status snapshot in a single call.
        Includes: current user info, active workspace, running timer (if any), and today's time entries.
        Use this FIRST instead of calling get_user_info, get_running_timer, and get_time_entries separately.
        """
        import datetime
        client = ClockifyClient(_resolve_api_key(api_key))
        ws_id = _resolve_workspace_id(workspace_id)

        # Fetch user info
        user = await client.get_current_user()
        user_id = user["id"]

        # Fetch running timer
        running_timer = await client.get_running_timer(ws_id, user_id)

        # Fetch today's entries
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
        entries = await client.get_time_entries(workspace_id=ws_id, user_id=user_id, start_time=today)

        return {
            "user": {"id": user_id, "name": user.get("name"), "email": user.get("email")},
            "workspace_id": ws_id,
            "running_timer": ClockifyClient.trim_time_entry(running_timer) if running_timer else None,
            "todays_entries": entries,  # Already trimmed by get_time_entries
            "todays_entry_count": len(entries),
        }
