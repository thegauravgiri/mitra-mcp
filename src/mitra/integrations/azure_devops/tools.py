"""Azure DevOps MCP tool registrations."""

from typing import Optional, List, Dict, Any

from mitra.integrations.azure_devops.client import AzureDevOpsClient
from mitra.integrations.azure_devops.context import get_azure_devops_pat, get_azure_devops_org


def _resolve_azure_config(pat: Optional[str] = None, organization_url: Optional[str] = None) -> tuple:
    """Resolve Azure DevOps PAT and org URL from parameters or environment variables."""
    resolved_pat = pat or get_azure_devops_pat()
    resolved_org = organization_url or get_azure_devops_org()
    if not resolved_pat:
        raise ValueError(
            "Azure DevOps PAT not found. Please provide the 'pat' parameter, "
            "set it via client headers, or set the AZURE_DEVOPS_PAT environment variable."
        )
    if not resolved_org:
        raise ValueError(
            "Azure DevOps organization URL not found. Please provide the 'organization_url' parameter, "
            "set it via client headers, or set the AZURE_DEVOPS_ORG environment variable."
        )
    return resolved_pat, resolved_org


def register_tools(mcp) -> None:
    """Register all Azure DevOps tools with the MCP server."""

    @mcp.tool()
    async def azure_devops_list_projects(
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists all projects in the Azure DevOps organization."""
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        return await client.list_projects()

    @mcp.tool()
    async def azure_devops_get_work_item(
        project: str, work_item_id: int,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches a single Azure DevOps work item (card) by its ID.
        Returns a clean summary with id, title, type, state, assigned_to, priority, tags, and URL.
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw = await client.get_work_item(project, work_item_id)
        return AzureDevOpsClient.format_work_item_summary(raw)

    @mcp.tool()
    async def azure_devops_create_work_item(
        project: str, work_item_type: str, title: str,
        description: Optional[str] = None, assigned_to: Optional[str] = None,
        state: Optional[str] = None, tags: Optional[str] = None,
        priority: Optional[int] = None, area_path: Optional[str] = None,
        iteration_path: Optional[str] = None,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new work item (card) in an Azure DevOps project.
        work_item_type can be 'Task', 'Bug', 'User Story', 'Product Backlog Item', 'Epic', 'Feature', etc.
        tags should be semicolon-separated (e.g., 'frontend;urgent').
        priority ranges from 1 (highest) to 4 (lowest).
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw = await client.create_work_item(
            project=project, work_item_type=work_item_type, title=title,
            description=description, assigned_to=assigned_to, state=state,
            tags=tags, priority=priority, area_path=area_path, iteration_path=iteration_path,
        )
        return AzureDevOpsClient.format_work_item_summary(raw)

    @mcp.tool()
    async def azure_devops_update_work_item(
        project: str, work_item_id: int,
        title: Optional[str] = None, description: Optional[str] = None,
        assigned_to: Optional[str] = None, state: Optional[str] = None,
        tags: Optional[str] = None, priority: Optional[int] = None,
        area_path: Optional[str] = None, iteration_path: Optional[str] = None,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates an existing Azure DevOps work item's details.
        Only the provided fields will be updated; other fields are preserved.
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw = await client.update_work_item(
            project=project, work_item_id=work_item_id, title=title,
            description=description, assigned_to=assigned_to, state=state,
            tags=tags, priority=priority, area_path=area_path, iteration_path=iteration_path,
        )
        return AzureDevOpsClient.format_work_item_summary(raw)

    @mcp.tool()
    async def azure_devops_update_work_item_state(
        project: str, work_item_id: int, state: str,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates only the state/status of an Azure DevOps work item.
        Common states: 'New', 'Active', 'Resolved', 'Closed', 'Removed'.
        Actual available states depend on the project's process template (Agile, Scrum, CMMI).
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw = await client.update_work_item_state(project, work_item_id, state)
        return AzureDevOpsClient.format_work_item_summary(raw)

    @mcp.tool()
    async def azure_devops_search_work_items(
        project: str, search_text: Optional[str] = None,
        work_item_type: Optional[str] = None, state: Optional[str] = None,
        assigned_to: Optional[str] = None, top: int = 50,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches Azure DevOps work items in a project using filters.
        Can filter by title text, work item type, state, and assignee.
        Use assigned_to='@me' to find items assigned to the authenticated user.
        Returns up to 'top' results (default 50).
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw_items = await client.search_work_items(
            project=project, search_text=search_text, work_item_type=work_item_type,
            state=state, assigned_to=assigned_to, top=top,
        )
        return [AzureDevOpsClient.format_work_item_summary(item) for item in raw_items]

    @mcp.tool()
    async def azure_devops_list_work_items_by_state(
        project: str, state: str, work_item_type: Optional[str] = None, top: int = 50,
        pat: Optional[str] = None, organization_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists Azure DevOps work items filtered by state in a project.
        Common states: 'New', 'Active', 'Resolved', 'Closed'.
        Optionally filter by work_item_type (e.g., 'Task', 'Bug').
        """
        resolved_pat, resolved_org = _resolve_azure_config(pat, organization_url)
        client = AzureDevOpsClient(resolved_pat, resolved_org)
        raw_items = await client.search_work_items(
            project=project, state=state, work_item_type=work_item_type, top=top,
        )
        return [AzureDevOpsClient.format_work_item_summary(item) for item in raw_items]
