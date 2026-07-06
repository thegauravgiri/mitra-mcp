"""WakaTime MCP tool registrations."""

from typing import Optional, List, Dict, Any

from mitra.clients.wakatime import WakaTimeClient
from mitra.context import get_wakatime_api_key


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    """Resolve WakaTime API key from parameter, request context, or env."""
    key = api_key or get_wakatime_api_key()
    if not key:
        raise ValueError(
            "WakaTime API Key not found. Please provide the 'api_key' parameter, "
            "set it via client headers, or set WAKATIME_API_KEY environment variable."
        )
    return key


def register(mcp) -> None:
    """Register all WakaTime tools with the MCP server."""

    @mcp.tool()
    async def wakatime_get_today_projects(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all projects worked on today and their total duration using WakaTime."""
        client = WakaTimeClient(_resolve_api_key(api_key))
        return await client.get_today_projects()

    @mcp.tool()
    async def wakatime_get_today_file_durations(
        project: Optional[str] = None, api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the file-level time breakdown (durations) for today using WakaTime.
        Can be filtered by a specific project name.
        """
        client = WakaTimeClient(_resolve_api_key(api_key))
        return await client.get_today_file_durations(project)

    @mcp.tool()
    async def wakatime_get_projects_for_range(
        start_date: str, end_date: str, api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists all projects worked on during the specified date range and their total duration using WakaTime.
        start_date and end_date should be in YYYY-MM-DD format.
        """
        client = WakaTimeClient(_resolve_api_key(api_key))
        return await client.get_projects_for_range(start_date, end_date)

    @mcp.tool()
    async def wakatime_get_file_durations_for_range(
        start_date: str, end_date: str, project: Optional[str] = None, api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the file-level time breakdown (durations) for the specified date range using WakaTime.
        Can be filtered by a specific project name.
        start_date and end_date should be in YYYY-MM-DD format.
        """
        client = WakaTimeClient(_resolve_api_key(api_key))
        return await client.get_file_durations_for_range(start_date, end_date, project)
