"""Google Calendar service client utilizing the multi-user credentials manager."""

import logging
from typing import Dict, Any, List, Optional
import httpx

from mitra.core.oauth_service import get_credential_service
from mitra.core.user import get_current_user_id

logger = logging.getLogger("mitra.integrations.google_calendar.service")


class GoogleCalendarService:
    """Service to interact with the Google Calendar API on behalf of the currently authenticated user."""

    def __init__(self) -> None:
        self.credential_service = get_credential_service()

    @staticmethod
    def trim_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only essential fields from a Google Calendar event to reduce token/payload size."""
        start = event.get("start", {})
        end = event.get("end", {})
        attendees = event.get("attendees", [])
        return {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "description": event.get("description"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "status": event.get("status"),
            "htmlLink": event.get("htmlLink"),
            "attendees": [a.get("email") for a in attendees if a.get("email")],
        }

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Obtain headers containing a valid refreshed access token for the active user."""
        user_id = await get_current_user_id()
        try:
            token = await self.credential_service.get_valid_access_token(user_id, "google")
        except ValueError as e:
            # Propagate meaningful connect instructions to the user/agent
            import os
            redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
            # Construct standard server base url from redirect_uri
            from urllib.parse import urlparse
            parsed = urlparse(redirect_uri)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            raise ValueError(
                f"Google Calendar has not been connected for this account.\n"
                f"Please visit: {base_url}/auth/google/start?user_id={user_id}\n"
                f"to authorize access."
            ) from e

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Helper to send HTTP requests to the Google Calendar API using user authorization headers."""
        headers = await self._get_auth_headers()
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params,
                    timeout=15.0,
                )
                if response.status_code >= 400:
                    logger.error(f"Google Calendar API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                if response.status_code == 204:
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"Google Calendar API call failed: {e.response.status_code} - {e.response.text}"
                ) from e
            except Exception as e:
                raise RuntimeError(f"Google Calendar API connection failed: {str(e)}") from e

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> List[Dict[str, Any]]:
        """List events from the specified calendar for the authenticated user."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max

        result = await self._request("GET", url, params=params)
        return result.get("items", [])

    async def create_event(
        self,
        calendar_id: str = "primary",
        summary: str = "",
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new event in the specified calendar for the authenticated user."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        
        body = {
            "summary": summary,
        }
        if description:
            body["description"] = description
        if start_time:
            body["start"] = {"dateTime": start_time}
        if end_time:
            body["end"] = {"dateTime": end_time}
        if attendees:
            body["attendees"] = [{"email": email} for email in attendees]

        return await self._request("POST", url, json_data=body)

    async def get_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Retrieves a specific calendar event."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
        return await self._request("GET", url)

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Deletes a specific calendar event."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
        await self._request("DELETE", url)
