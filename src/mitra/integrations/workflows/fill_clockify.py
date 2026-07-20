"""Composite fill-clockify tools that bundle multiple API calls into single MCP tool invocations."""

import datetime
import logging
from typing import Optional, List, Dict, Any

from mitra.integrations.clockify.client import ClockifyClient
from mitra.integrations.wakatime.client import WakaTimeClient
from mitra.integrations.azure_devops.client import AzureDevOpsClient
from mitra.integrations.azure_devops.tools import _resolve_azure_config
from mitra.integrations.clockify.context import (
    get_clockify_api_key, get_workspace_id, get_project_id,
)
from mitra.integrations.wakatime.context import get_wakatime_api_key
from mitra.integrations.google_calendar.service import GoogleCalendarService

logger = logging.getLogger("mitra.integrations.workflows")


def _resolve_clockify(api_key: Optional[str], workspace_id: Optional[str]) -> tuple:
    """Resolve Clockify API key and workspace ID."""
    key = api_key or get_clockify_api_key()
    if not key:
        raise ValueError("Clockify API Key not found.")
    ws = workspace_id or get_workspace_id()
    if not ws:
        raise ValueError("Clockify Workspace ID not found.")
    return key, ws


def register_tools(mcp) -> None:
    """Register composite fill-clockify tools with the MCP server."""

    @mcp.tool()
    async def clockify_fill_timesheet(
        date: Optional[str] = None,
        date_end: Optional[str] = None,
        azure_project: Optional[str] = None,
        clockify_project_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        clockify_api_key: Optional[str] = None,
        wakatime_api_key: Optional[str] = None,
        azure_pat: Optional[str] = None,
        azure_organization_url: Optional[str] = None,
        google_calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        High-level composite tool for filling Clockify timesheets. Performs ALL data gathering
        in a single call and returns a structured fill plan for the agent to confirm with the user.

        This tool does the following server-side:
        1. Fetches WakaTime coding activity for the date (default: today)
        2. Gets current Clockify status (running timer, existing entries)
        3. Fetches active Azure DevOps cards assigned to the user (if azure_project provided)
        4. Fetches Google Calendar events for the date range (if google credentials provided)
        5. Returns a structured plan with suggested time entries

        The agent should present this plan to the user, then call clockify_execute_fill_plan
        or clockify_log_time_for_card / clockify_add_time_entry to create the entries.

        Args:
            date: Date to fill for in YYYY-MM-DD format. Defaults to today.
            date_end: Optional end date for a range. Defaults to same as date.
            azure_project: Azure DevOps project name to fetch active cards from.
            clockify_project_id: Clockify project ID to assign entries to. Falls back to env CLOCKIFY_PROJECT_ID.
            workspace_id: Clockify workspace ID. Falls back to env.
            clockify_api_key: Clockify API key. Falls back to env.
            wakatime_api_key: WakaTime API key. Falls back to env/config.
            azure_pat: Azure DevOps PAT. Falls back to env.
            azure_organization_url: Azure DevOps org URL. Falls back to env.
            google_access_token: Google access token. Falls back to env.
            google_refresh_token: Google refresh token. Falls back to env.
            google_client_id: Google client ID. Falls back to env.
            google_client_secret: Google client secret. Falls back to env.
            google_calendar_id: Google Calendar ID. Defaults to "primary".
        """
        # Resolve dates
        target_date = date or datetime.datetime.now().strftime("%Y-%m-%d")
        end_date = date_end or target_date

        warnings = []
        try:
            dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
            if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
                warnings.append(
                    f"Target date {target_date} is a weekend ({dt.strftime('%A')}). "
                    "Clockify should ONLY be filled from Monday to Friday unless explicitly requested."
                )
        except ValueError:
            pass

        result: Dict[str, Any] = {
            "date_range": {"start": target_date, "end": end_date},
            "fill_rules": {
                "allowed_days": "Monday to Friday",
                "break_time_window": "13:30 - 15:00 (1:30 PM - 3:00 PM)",
                "break_time_note": "Do not fill time from 1:30 PM to 3:00 PM unless there is a proven work record or explicitly specified by input.",
                "verification_required": True,
            },
            "warnings": warnings,
            "wakatime_activity": None,
            "clockify_status": None,
            "azure_active_cards": None,
            "google_calendar_events": None,
            "errors": [],
        }

        # 1. Fetch WakaTime activity
        waka_key = wakatime_api_key or get_wakatime_api_key()
        if waka_key:
            try:
                waka_client = WakaTimeClient(waka_key)
                projects = await waka_client.get_projects_for_range(target_date, end_date)
                result["wakatime_activity"] = {
                    "projects": projects,
                    "total_seconds": sum(p.get("total_seconds", 0) for p in projects),
                }
            except Exception as e:
                result["errors"].append(f"WakaTime fetch failed: {str(e)}")
        else:
            result["errors"].append("WakaTime API key not configured — skipping activity fetch.")

        # 2. Fetch Clockify status (user, running timer, existing entries for the date)
        ck_key, ws_id = _resolve_clockify(clockify_api_key, workspace_id)
        try:
            ck_client = ClockifyClient(ck_key)
            user = await ck_client.get_current_user()
            user_id = user["id"]

            running_timer = await ck_client.get_running_timer(ws_id, user_id)

            day_start = f"{target_date}T00:00:00Z"
            day_end = f"{end_date}T23:59:59Z"
            existing_entries = await ck_client.get_time_entries(
                workspace_id=ws_id, user_id=user_id,
                start_time=day_start, end_time=day_end,
            )

            result["clockify_status"] = {
                "user": {"id": user_id, "name": user.get("name")},
                "workspace_id": ws_id,
                "clockify_project_id": clockify_project_id or get_project_id(),
                "running_timer": ClockifyClient.trim_time_entry(running_timer) if running_timer else None,
                "existing_entries": existing_entries,  # Already trimmed
                "existing_entry_count": len(existing_entries),
            }
        except Exception as e:
            result["errors"].append(f"Clockify status fetch failed: {str(e)}")

        # 3. Fetch Azure DevOps active cards (if project specified)
        if azure_project:
            try:
                resolved_pat, resolved_org = _resolve_azure_config(azure_pat, azure_organization_url)
                azure_client = AzureDevOpsClient(resolved_pat, resolved_org)
                raw_items = await azure_client.search_work_items(
                    project=azure_project, assigned_to="@me", state="Active", top=25,
                )
                result["azure_active_cards"] = [
                    AzureDevOpsClient.format_work_item_summary(item) for item in raw_items
                ]
            except Exception as e:
                result["errors"].append(f"Azure DevOps fetch failed: {str(e)}")

        # 4. Fetch Google Calendar events (if connected for user)
        try:
            google_service = GoogleCalendarService()
            time_min = f"{target_date}T00:00:00Z"
            time_max = f"{end_date}T23:59:59Z"
            events = await google_service.list_events(
                calendar_id=google_calendar_id,
                time_min=time_min,
                time_max=time_max
            )
            result["google_calendar_events"] = [
                GoogleCalendarService.trim_event(e) for e in events
            ]
        except Exception as e:
            # Catch gracefully so missing auth doesn't crash the entire plan
            result["errors"].append(f"Google Calendar fetch skipped: {str(e)}")

        return result

    @mcp.tool()
    async def clockify_batch_create_entries(
        entries: List[Dict[str, Any]],
        stop_running_timer: bool = True,
        workspace_id: Optional[str] = None,
        clockify_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Batch-creates multiple Clockify time entries in a single tool call.
        Use this after reviewing the plan from clockify_fill_timesheet.

        Each entry in the list should have:
        - start_time: ISO 8601 UTC (e.g., "2024-01-15T09:00:00Z")
        - end_time: ISO 8601 UTC (e.g., "2024-01-15T11:00:00Z")
        - description: Entry description (e.g., "project-42: Fix login bug")
        - project_id: (Optional) Clockify project ID
        - billable: (Optional) Boolean, defaults to True

        Args:
            entries: List of entry dicts with start_time, end_time, description, etc.
            stop_running_timer: If True, stops any running timer before creating entries.
            workspace_id: Clockify workspace ID.
            clockify_api_key: Clockify API key.
        """
        ck_key, ws_id = _resolve_clockify(clockify_api_key, workspace_id)
        client = ClockifyClient(ck_key)

        results = {"created": [], "errors": [], "stopped_timer": None}

        # Optionally stop running timer
        if stop_running_timer:
            try:
                user = await client.get_current_user()
                user_id = user["id"]
                running = await client.get_running_timer(ws_id, user_id)
                if running:
                    stopped = await client.stop_running_timer(ws_id, user_id)
                    results["stopped_timer"] = ClockifyClient.trim_time_entry(stopped) if stopped else "stopped"
            except Exception as e:
                results["errors"].append(f"Failed to stop running timer: {str(e)}")

        # Create all entries
        for i, entry in enumerate(entries):
            try:
                created = await client.add_time_entry(
                    workspace_id=ws_id,
                    start_time=entry["start_time"],
                    end_time=entry.get("end_time"),
                    description=entry.get("description", ""),
                    project_id=entry.get("project_id"),
                    task_id=entry.get("task_id"),
                    billable=entry.get("billable", True),
                )
                results["created"].append(ClockifyClient.trim_time_entry(created))
            except Exception as e:
                results["errors"].append(f"Entry {i + 1} failed: {str(e)}")

        results["total_created"] = len(results["created"])
        results["total_errors"] = len(results["errors"])
        return results
