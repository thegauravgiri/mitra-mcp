"""Google Calendar MCP tool registrations."""

from typing import Optional, List, Dict, Any

from mitra.integrations.google_calendar.service import GoogleCalendarService
from mitra.core.user import get_current_user_id


def register_tools(mcp) -> None:
    """Register all Google Calendar tools with the MCP server."""

    @mcp.tool()
    async def google_calendar_connect() -> Dict[str, str]:
        """
        Returns the authorization URL to connect your Google Calendar account.
        Use this tool when calendar credentials are missing or need reconnection.
        """
        import os
        from urllib.parse import urlparse
        
        user_id = await get_current_user_id()
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
        parsed = urlparse(redirect_uri)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        auth_url = f"{base_url}/auth/google/start?user_id={user_id}"
        
        return {
            "status": "connect_required",
            "message": "Please authorize Google Calendar by visiting the connection URL.",
            "url": auth_url,
        }

    @mcp.tool()
    async def google_calendar_list_events(
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        Lists events from Google Calendar for the authenticated user.
        time_min and time_max must be in ISO 8601 format (e.g., YYYY-MM-DDTHH:MM:SSZ).
        """
        service = GoogleCalendarService()
        events = await service.list_events(
            calendar_id=calendar_id, time_min=time_min, time_max=time_max, max_results=max_results
        )
        return [GoogleCalendarService.trim_event(e) for e in events]

    @mcp.tool()
    async def google_calendar_create_event(
        calendar_id: str = "primary",
        summary: str = "",
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new event in Google Calendar for the authenticated user.
        start_time and end_time must be in ISO 8601 format (e.g., YYYY-MM-DDTHH:MM:SSZ).
        """
        import datetime
        service = GoogleCalendarService()

        # Resolve start/end times if not provided
        st_time = start_time or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not end_time:
            # Default to 1 hour after start
            clean_st = st_time.replace("Z", "+00:00")
            parsed_st = datetime.datetime.fromisoformat(clean_st)
            parsed_end = parsed_st + datetime.timedelta(hours=1)
            e_time = parsed_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            e_time = end_time

        event = await service.create_event(
            calendar_id=calendar_id,
            summary=summary,
            description=description,
            start_time=st_time,
            end_time=e_time,
            attendees=attendees,
        )
        return GoogleCalendarService.trim_event(event)

    @mcp.tool()
    async def google_calendar_get_event(
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """Retrieves a specific Google Calendar event by ID for the authenticated user."""
        service = GoogleCalendarService()
        event = await service.get_event(calendar_id=calendar_id, event_id=event_id)
        return GoogleCalendarService.trim_event(event)

    @mcp.tool()
    async def google_calendar_delete_event(
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """Deletes a Google Calendar event by ID for the authenticated user."""
        service = GoogleCalendarService()
        await service.delete_event(calendar_id=calendar_id, event_id=event_id)
        return {"status": "success", "message": f"Deleted event {event_id}"}
