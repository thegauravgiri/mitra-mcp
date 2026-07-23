import httpx
import base64
import re
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("mitra.integrations.azure_devops")

API_VERSION = "7.0"


class AzureDevOpsClient:
    """Client for Azure DevOps REST API using Personal Access Token (PAT) authentication."""

    def __init__(self, pat: str, organization_url: str):
        """
        Args:
            pat: Personal Access Token for authentication.
            organization_url: Organization URL (e.g., https://dev.azure.com/your-org).
        """
        self.pat = pat
        self.organization_url = organization_url.rstrip("/")
        credentials = base64.b64encode(f":{pat}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }
        self.patch_headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json-patch+json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        use_patch_content_type: bool = False,
    ) -> Any:
        if params is None:
            params = {}
        params["api-version"] = API_VERSION
        headers = self.patch_headers if use_patch_content_type else self.headers

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method, url=url, headers=headers,
                    json=json_data, params=params, timeout=30.0,
                )
                if response.status_code >= 400:
                    logger.error(f"Azure DevOps API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                if response.status_code == 204:
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Azure DevOps API call failed: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise RuntimeError(f"Azure DevOps connection failed: {str(e)}")

    # --- Project Operations ---

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in the organization."""
        url = f"{self.organization_url}/_apis/projects"
        result = await self._request("GET", url)
        return result.get("value", [])

    async def get_project(self, project_name: str) -> Dict[str, Any]:
        """Get a single project's details by name or ID."""
        url = f"{self.organization_url}/_apis/projects/{project_name}"
        return await self._request("GET", url)

    # --- Work Item Operations ---

    async def get_work_item(self, project: str, work_item_id: int, expand: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a single work item by ID.

        Args:
            expand: Optional expansion. Use "All" for full details (relations, attachments).
                    Default is None for a lightweight response (fields only).
        """
        url = f"{self.organization_url}/{project}/_apis/wit/workitems/{work_item_id}"
        params = {}
        if expand:
            params["$expand"] = expand
        return await self._request("GET", url, params=params)

    async def create_work_item(
        self, project: str, work_item_type: str, title: str,
        description: Optional[str] = None, assigned_to: Optional[str] = None,
        state: Optional[str] = None, tags: Optional[str] = None,
        priority: Optional[int] = None, area_path: Optional[str] = None,
        iteration_path: Optional[str] = None,
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new work item (card) in a project."""
        url = f"{self.organization_url}/{project}/_apis/wit/workitems/${work_item_type}"
        operations = [{"op": "add", "path": "/fields/System.Title", "value": title}]

        field_map = {
            "/fields/System.Description": description,
            "/fields/System.AssignedTo": assigned_to,
            "/fields/System.State": state,
            "/fields/System.Tags": tags,
            "/fields/Microsoft.VSTS.Common.Priority": priority,
            "/fields/System.AreaPath": area_path,
            "/fields/System.IterationPath": iteration_path,
        }
        for path, value in field_map.items():
            if value is not None:
                operations.append({"op": "add", "path": path, "value": value})

        if parent_id is not None:
            parent_url = f"{self.organization_url}/_apis/wit/workitems/{parent_id}"
            operations.append({
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_url,
                    "attributes": {
                        "comment": "Parent linkage"
                    }
                }
            })

        return await self._request("POST", url, json_data=operations, use_patch_content_type=True)

    async def update_work_item(
        self, project: str, work_item_id: int,
        title: Optional[str] = None, description: Optional[str] = None,
        assigned_to: Optional[str] = None, state: Optional[str] = None,
        tags: Optional[str] = None, priority: Optional[int] = None,
        area_path: Optional[str] = None, iteration_path: Optional[str] = None,
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update an existing work item's fields. Only provided fields are changed."""
        url = f"{self.organization_url}/{project}/_apis/wit/workitems/{work_item_id}"

        field_map = {
            "/fields/System.Title": title,
            "/fields/System.Description": description,
            "/fields/System.AssignedTo": assigned_to,
            "/fields/System.State": state,
            "/fields/System.Tags": tags,
            "/fields/Microsoft.VSTS.Common.Priority": priority,
            "/fields/System.AreaPath": area_path,
            "/fields/System.IterationPath": iteration_path,
        }
        operations = [
            {"op": "replace", "path": path, "value": value}
            for path, value in field_map.items()
            if value is not None
        ]

        if parent_id is not None:
            parent_url = f"{self.organization_url}/_apis/wit/workitems/{parent_id}"
            operations.append({
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_url,
                    "attributes": {
                        "comment": "Parent linkage"
                    }
                }
            })

        if not operations:
            raise ValueError("At least one field must be provided to update.")

        return await self._request("PATCH", url, json_data=operations, use_patch_content_type=True)

    async def update_work_item_state(self, project: str, work_item_id: int, state: str) -> Dict[str, Any]:
        """Update only the state/status of a work item."""
        return await self.update_work_item(project=project, work_item_id=work_item_id, state=state)

    async def add_work_item_relation(
        self, project: str, work_item_id: int, relation_work_item_id: int, relation_type: str = "parent"
    ) -> Dict[str, Any]:
        """Add a parent or child relation between two work items."""
        url = f"{self.organization_url}/{project}/_apis/wit/workitems/{work_item_id}"
        
        if relation_type.lower() == "parent":
            rel_name = "System.LinkTypes.Hierarchy-Reverse"
        elif relation_type.lower() == "child":
            rel_name = "System.LinkTypes.Hierarchy-Forward"
        else:
            rel_name = relation_type

        parent_url = f"{self.organization_url}/_apis/wit/workitems/{relation_work_item_id}"
        operations = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": rel_name,
                    "url": parent_url,
                    "attributes": {
                        "comment": f"Linked via Mitra MCP as {relation_type}"
                    }
                }
            }
        ]
        return await self._request("PATCH", url, json_data=operations, use_patch_content_type=True)

    async def query_work_items(self, project: str, wiql_query: str) -> List[Dict[str, Any]]:
        """Query work items using WIQL. Returns full details for matched items."""
        url = f"{self.organization_url}/{project}/_apis/wit/wiql"
        result = await self._request("POST", url, json_data={"query": wiql_query})
        work_items = result.get("workItems", [])
        if not work_items:
            return []
        ids = [wi["id"] for wi in work_items[:200]]
        return await self._get_work_items_batch(project, ids)

    async def _get_work_items_batch(self, project: str, ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch multiple work items by their IDs."""
        if not ids:
            return []
        url = f"{self.organization_url}/{project}/_apis/wit/workitems"
        params = {"ids": ",".join(str(i) for i in ids), "$expand": "All"}
        result = await self._request("GET", url, params=params)
        return result.get("value", [])

    async def search_work_items(
        self, project: str, search_text: Optional[str] = None,
        work_item_type: Optional[str] = None, state: Optional[str] = None,
        assigned_to: Optional[str] = None, top: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search work items in a project using common filters."""
        conditions = [f"[System.TeamProject] = '{project}'"]
        if search_text:
            conditions.append(f"[System.Title] CONTAINS '{search_text.replace(chr(39), chr(39)*2)}'")
        if work_item_type:
            conditions.append(f"[System.WorkItemType] = '{work_item_type}'")
        if state:
            conditions.append(f"[System.State] = '{state}'")
        if assigned_to:
            if assigned_to.lower() == "@me":
                conditions.append("[System.AssignedTo] = @me")
            else:
                conditions.append(f"[System.AssignedTo] = '{assigned_to}'")

        wiql = f"SELECT [System.Id] FROM WorkItems WHERE {' AND '.join(conditions)} ORDER BY [System.ChangedDate] DESC"
        url = f"{self.organization_url}/{project}/_apis/wit/wiql"
        result = await self._request("POST", url, json_data={"query": wiql}, params={"$top": top})
        work_items = result.get("workItems", [])
        if not work_items:
            return []
        return await self._get_work_items_batch(project, [wi["id"] for wi in work_items])

    # --- Utility Methods ---

    @staticmethod
    def format_work_item_summary(work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a clean summary from a raw Azure DevOps work item response."""
        fields = work_item.get("fields", {})
        assigned = fields.get("System.AssignedTo")
        return {
            "id": work_item.get("id"),
            "title": fields.get("System.Title"),
            "type": fields.get("System.WorkItemType"),
            "state": fields.get("System.State"),
            "assigned_to": assigned.get("displayName") if isinstance(assigned, dict) else assigned,
            "priority": fields.get("Microsoft.VSTS.Common.Priority"),
            "tags": fields.get("System.Tags"),
            "area_path": fields.get("System.AreaPath"),
            "iteration_path": fields.get("System.IterationPath"),
            "description": fields.get("System.Description"),
            "url": work_item.get("_links", {}).get("html", {}).get("href"),
            "created_date": fields.get("System.CreatedDate"),
            "changed_date": fields.get("System.ChangedDate"),
        }

    @staticmethod
    def generate_project_slug(project_name: str) -> str:
        """
        Generate a short project slug from the project name.
        Skips generic prefix tokens like 'gl' and 'we' to extract the primary project key.

        Examples:
            'gl-we-dhchat-backend' -> 'dhchat'
            'Customer Portal' -> 'customer'
        """
        parts = [p.lower() for p in re.split(r"[\s\-_]+", project_name.strip()) if p]
        ignored_prefixes = {"gl", "we", "app", "svc", "service", "prj", "project"}
        target_part = None
        for p in parts:
            if p not in ignored_prefixes:
                target_part = p
                break
        slug = target_part if target_part else (parts[0] if parts else project_name.lower())
        return re.sub(r"[^a-z0-9]", "", slug)

    @staticmethod
    def format_clockify_description(project_slug: str, work_item_id: int, title: str) -> str:
        """
        Format a Clockify description linking to an Azure DevOps work item.
        Format: <project-slug>-<card_no>: <card_title>
        """
        return f"{project_slug}-{work_item_id}: {title}"
