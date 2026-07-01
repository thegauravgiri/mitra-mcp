import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger("mitra.clockify")
BASE_URL = "https://api.clockify.me/api/v1"

class ClockifyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, path: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data,
                    params=params,
                    timeout=15.0
                )
                if response.status_code >= 400:
                    logger.error(f"Clockify API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                if response.status_code == 204:
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Clockify API call failed: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise RuntimeError(f"Clockify connection failed: {str(e)}")

    async def get_current_user(self) -> Dict[str, Any]:
        """Gets user profile info for the authenticated user."""
        return await self._request("GET", "user")

    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Gets all workspaces for the authenticated user."""
        return await self._request("GET", "workspaces")

    async def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Gets all projects in a workspace."""
        return await self._request("GET", f"workspaces/{workspace_id}/projects")

    async def add_time_entry(
        self,
        workspace_id: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: str = "",
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        billable: bool = True
    ) -> Dict[str, Any]:
        """
        Creates a time entry in a workspace.
        If end_time is not provided, the timer will be running.
        start_time and end_time should be in ISO 8601 UTC format (e.g. YYYY-MM-DDTHH:MM:SSZ).
        """
        payload: Dict[str, Any] = {
            "start": start_time,
            "description": description,
            "billable": billable
        }
        if end_time:
            payload["end"] = end_time
        if project_id:
            payload["projectId"] = project_id
        if task_id:
            payload["taskId"] = task_id

        return await self._request("POST", f"workspaces/{workspace_id}/time-entries", json_data=payload)

    async def get_running_timer(self, workspace_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the running time entry for a user in a workspace, if any."""
        params = {"in-progress": "true"}
        entries = await self._request("GET", f"workspaces/{workspace_id}/user/{user_id}/time-entries", params=params)
        if entries and isinstance(entries, list):
            return entries[0]
        return None

    async def stop_running_timer(self, workspace_id: str, user_id: str, end_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Stops the currently running timer for the user by setting its end time."""
        if not end_time:
            end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "end": end_time
        }
        return await self._request("PATCH", f"workspaces/{workspace_id}/user/{user_id}/time-entries", json_data=payload)

    async def get_time_entry(self, workspace_id: str, time_entry_id: str) -> Dict[str, Any]:
        """Retrieves a specific time entry by ID."""
        return await self._request("GET", f"workspaces/{workspace_id}/time-entries/{time_entry_id}")

    async def update_time_entry(
        self,
        workspace_id: str,
        time_entry_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        billable: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Updates an existing time entry in a workspace.
        Only the provided parameters will be updated; other fields will be preserved.
        """
        # Fetch the existing time entry first to ensure we don't overwrite/clear other fields.
        existing = await self.get_time_entry(workspace_id, time_entry_id)

        # Extract existing values
        start = start_time if start_time is not None else existing.get("timeInterval", {}).get("start")
        end = end_time if end_time is not None else existing.get("timeInterval", {}).get("end")
        desc = description if description is not None else existing.get("description")
        proj_id = project_id if project_id is not None else existing.get("projectId")
        t_id = task_id if task_id is not None else existing.get("taskId")
        is_billable = billable if billable is not None else existing.get("billable")

        # Construct update payload
        payload: Dict[str, Any] = {
            "start": start,
            "description": desc,
            "billable": is_billable
        }
        if end:
            payload["end"] = end
        if proj_id:
            payload["projectId"] = proj_id
        if t_id:
            payload["taskId"] = t_id

        return await self._request("PUT", f"workspaces/{workspace_id}/time-entries/{time_entry_id}", json_data=payload)

    async def get_time_entries(
        self,
        workspace_id: str,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves time entries for a user in a workspace, filtered by date range and project.
        If user_id is not provided, retrieves entries for the authenticated user.
        start_time and end_time must be in ISO 8601 UTC format (e.g. YYYY-MM-DDTHH:MM:SSZ).
        """
        if not user_id:
            user = await self.get_current_user()
            user_id = user["id"]

        params: Dict[str, Any] = {
            "page-size": 1000  # Fetch a large page to avoid missing entries
        }
        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time

        entries = await self._request("GET", f"workspaces/{workspace_id}/user/{user_id}/time-entries", params=params)

        if not entries or not isinstance(entries, list):
            return []

        if project_id:
            # Filter by project ID
            entries = [e for e in entries if e.get("projectId") == project_id]

        return entries


