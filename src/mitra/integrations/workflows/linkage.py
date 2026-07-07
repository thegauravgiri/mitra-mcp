"""Cross-integration linkage tools (Clockify + Azure DevOps)."""

from typing import Optional, Dict, Any

from mitra.integrations.clockify.client import ClockifyClient
from mitra.integrations.azure_devops.client import AzureDevOpsClient
from mitra.integrations.azure_devops.tools import _resolve_azure_config
from mitra.integrations.clockify.context import get_clockify_api_key, get_workspace_id


def register_tools(mcp) -> None:
    """Register cross-integration linkage tools with the MCP server."""

    @mcp.tool()
    async def clockify_log_time_for_card(
        project_name: str,
        work_item_id: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        workspace_id: Optional[str] = None,
        clockify_project_id: Optional[str] = None,
        billable: bool = True,
        clockify_api_key: Optional[str] = None,
        azure_pat: Optional[str] = None,
        azure_organization_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convenience tool that logs a Clockify time entry linked to an Azure DevOps work item (card).
        Automatically formats the description as '<project-slug>-<card_no>: <card_title>'.

        Args:
            project_name: Azure DevOps project name (used to fetch the card and generate the slug).
            work_item_id: Azure DevOps work item ID (card number).
            start_time: Start time in ISO 8601 UTC (e.g., YYYY-MM-DDTHH:MM:SSZ). Optional, defaults to now.
            end_time: End time in ISO 8601 UTC (optional; omit to start a running timer).
            workspace_id: Clockify workspace ID. If omitted, resolved from context.
            clockify_project_id: Clockify project ID to assign the entry to.
            billable: Whether the time entry is billable.
        """
        import datetime

        # 1. Fetch the work item from Azure DevOps
        resolved_pat, resolved_org = _resolve_azure_config(azure_pat, azure_organization_url)
        azure_client = AzureDevOpsClient(resolved_pat, resolved_org)
        work_item = await azure_client.get_work_item(project_name, work_item_id)
        title = work_item.get("fields", {}).get("System.Title", "Untitled")

        # 2. Generate the formatted description
        slug = AzureDevOpsClient.generate_project_slug(project_name)
        description = AzureDevOpsClient.format_clockify_description(slug, work_item_id, title)

        # 3. Create the Clockify time entry
        clockify_key = clockify_api_key or get_clockify_api_key()
        if not clockify_key:
            raise ValueError(
                "Clockify API Key not found. Please provide the 'clockify_api_key' parameter, "
                "set it via client headers, or set CLOCKIFY_API_KEY environment variable."
            )

        resolved_ws_id = workspace_id or get_workspace_id()
        if not resolved_ws_id:
            raise ValueError(
                "Clockify Workspace ID not found. Please provide the 'workspace_id' parameter, "
                "set it via client headers, or set CLOCKIFY_WORKSPACE_ID environment variable."
            )

        clockify_client = ClockifyClient(clockify_key)

        # Default start_time to now if not provided
        st_time = start_time or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        entry = await clockify_client.add_time_entry(
            workspace_id=resolved_ws_id, start_time=st_time, end_time=end_time,
            description=description, project_id=clockify_project_id, billable=billable,
        )

        return {
            "clockify_entry": entry,
            "formatted_description": description,
            "azure_work_item": AzureDevOpsClient.format_work_item_summary(work_item),
        }
