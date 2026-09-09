import httpx
import base64
from typing import Dict, Any, List, Optional, Union
import logging

logger = logging.getLogger("mitra.integrations.jira")

API_VERSION = "3"


class JiraClient:
    """Client for the Jira Cloud REST API (v3) using email + API token (Basic auth)."""

    def __init__(self, email: str, api_token: str, site_url: str):
        """
        Args:
            email: Atlassian account email associated with the API token.
            api_token: Atlassian API token for authentication.
            site_url: Jira site base URL (e.g. https://your-domain.atlassian.net).
        """
        self.email = email
        self.api_token = api_token
        self.site_url = site_url.rstrip("/")
        self.base_url = f"{self.site_url}/rest/api/{API_VERSION}"
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method, url=url, headers=self.headers,
                    json=json_data, params=params, timeout=30.0,
                )
                if response.status_code >= 400:
                    logger.error(f"Jira API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Jira API call failed: {e.response.status_code} - {e.response.text}")
            except httpx.HTTPError as e:
                raise RuntimeError(f"Jira connection failed: {str(e)}")

    # --- ADF (Atlassian Document Format) helpers ---

    @staticmethod
    def text_to_adf(text: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Wrap plain text into a minimal Atlassian Document Format document.

        If a dict is passed (an already-built ADF document), it is returned as-is.
        """
        if isinstance(text, dict):
            return text
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }

    @staticmethod
    def adf_to_text(adf: Optional[Union[Dict[str, Any], str]]) -> Optional[str]:
        """Best-effort extraction of plain text from an Atlassian Document Format document."""
        if adf is None:
            return None
        if isinstance(adf, str):
            return adf

        parts: List[str] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "text" and "text" in node:
                    parts.append(node["text"])
                for child in node.get("content", []) or []:
                    _walk(child)
            elif isinstance(node, list):
                for child in node:
                    _walk(child)

        _walk(adf)
        return "".join(parts) if parts else None

    # --- User Operations ---

    async def get_current_user(self) -> Dict[str, Any]:
        """Fetch the authenticated user's profile. Useful for verifying credentials."""
        url = f"{self.base_url}/myself"
        return await self._request("GET", url)

    async def find_account_id(self, query: str) -> Optional[str]:
        """Resolve an email address or display name to a Jira accountId."""
        url = f"{self.base_url}/user/search"
        result = await self._request("GET", url, params={"query": query})
        if isinstance(result, list) and result:
            return result[0].get("accountId")
        return None

    # --- Project Operations ---

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects visible to the authenticated user."""
        url = f"{self.base_url}/project/search"
        result = await self._request("GET", url, params={"maxResults": 100})
        return result.get("values", []) if isinstance(result, dict) else []

    async def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get a single project's details by key or ID."""
        url = f"{self.base_url}/project/{project_key}"
        return await self._request("GET", url)

    async def list_issue_types(self, project_key: str) -> List[Dict[str, Any]]:
        """List issue types available to a project (via project details)."""
        project = await self.get_project(project_key)
        return project.get("issueTypes", [])

    # --- Issue Operations ---

    async def get_issue(self, issue_key: str, expand: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a single issue by key (e.g. 'PROJ-123') or ID."""
        url = f"{self.base_url}/issue/{issue_key}"
        params = {}
        if expand:
            params["expand"] = expand
        return await self._request("GET", url, params=params)

    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: Optional[Union[str, Dict[str, Any]]] = None,
        assignee_account_id: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        parent_key: Optional[str] = None,
        components: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new issue in a project.

        parent_key links this issue as a sub-task of an existing issue (issue_type must be a sub-task type).
        """
        url = f"{self.base_url}/issue"
        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if description is not None:
            fields["description"] = self.text_to_adf(description)
        if assignee_account_id is not None:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority is not None:
            fields["priority"] = {"name": priority}
        if labels is not None:
            fields["labels"] = labels
        if components is not None:
            fields["components"] = [{"name": c} for c in components]
        if parent_key is not None:
            fields["parent"] = {"key": parent_key}
        if custom_fields:
            fields.update(custom_fields)

        return await self._request("POST", url, json_data={"fields": fields})

    async def update_issue(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        description: Optional[Union[str, Dict[str, Any]]] = None,
        assignee_account_id: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update an existing issue's fields. Only provided fields are changed."""
        url = f"{self.base_url}/issue/{issue_key}"
        fields: Dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = self.text_to_adf(description)
        if assignee_account_id is not None:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority is not None:
            fields["priority"] = {"name": priority}
        if labels is not None:
            fields["labels"] = labels
        if components is not None:
            fields["components"] = [{"name": c} for c in components]
        if custom_fields:
            fields.update(custom_fields)

        if not fields:
            raise ValueError("At least one field must be provided to update.")

        await self._request("PUT", url, json_data={"fields": fields})

    async def delete_issue(self, issue_key: str, delete_subtasks: bool = True) -> None:
        """Permanently delete an issue."""
        url = f"{self.base_url}/issue/{issue_key}"
        await self._request("DELETE", url, params={"deleteSubtasks": str(delete_subtasks).lower()})

    async def assign_issue(self, issue_key: str, account_id: Optional[str]) -> None:
        """Assign (or unassign, if account_id is None) an issue."""
        url = f"{self.base_url}/issue/{issue_key}/assignee"
        await self._request("PUT", url, json_data={"accountId": account_id})

    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[List[str]] = None,
        next_page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search issues using JQL via the enhanced /search/jql endpoint.

        Returns the raw response, which includes 'issues' and a 'nextPageToken' for pagination.
        """
        url = f"{self.base_url}/search/jql"
        payload: Dict[str, Any] = {"jql": jql, "maxResults": max_results}
        payload["fields"] = fields if fields is not None else ["*navigable"]
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        return await self._request("POST", url, json_data=payload)

    # --- Transition Operations ---

    async def list_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """List available workflow transitions for an issue."""
        url = f"{self.base_url}/issue/{issue_key}/transitions"
        result = await self._request("GET", url)
        return result.get("transitions", []) if isinstance(result, dict) else []

    async def transition_issue(
        self, issue_key: str, transition: str, comment: Optional[Union[str, Dict[str, Any]]] = None
    ) -> None:
        """Move an issue through its workflow.

        `transition` may be a transition ID or its (case-insensitive) name, e.g. 'Done', 'In Progress'.
        """
        transition_id = transition
        if not str(transition).isdigit():
            available = await self.list_transitions(issue_key)
            match = next(
                (t for t in available if t.get("name", "").lower() == transition.lower()), None
            )
            if not match:
                names = ", ".join(t.get("name", "") for t in available)
                raise ValueError(f"Unknown transition '{transition}'. Available transitions: {names}")
            transition_id = match["id"]

        url = f"{self.base_url}/issue/{issue_key}/transitions"
        payload: Dict[str, Any] = {"transition": {"id": str(transition_id)}}
        if comment is not None:
            payload["update"] = {
                "comment": [{"add": {"body": self.text_to_adf(comment)}}]
            }
        await self._request("POST", url, json_data=payload)

    # --- Comment Operations ---

    async def list_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """List all comments on an issue."""
        url = f"{self.base_url}/issue/{issue_key}/comment"
        result = await self._request("GET", url)
        return result.get("comments", []) if isinstance(result, dict) else []

    async def add_comment(self, issue_key: str, body: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Add a comment to an issue."""
        url = f"{self.base_url}/issue/{issue_key}/comment"
        return await self._request("POST", url, json_data={"body": self.text_to_adf(body)})

    async def update_comment(
        self, issue_key: str, comment_id: str, body: Union[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update an existing comment on an issue."""
        url = f"{self.base_url}/issue/{issue_key}/comment/{comment_id}"
        return await self._request("PUT", url, json_data={"body": self.text_to_adf(body)})

    async def delete_comment(self, issue_key: str, comment_id: str) -> None:
        """Delete a comment from an issue."""
        url = f"{self.base_url}/issue/{issue_key}/comment/{comment_id}"
        await self._request("DELETE", url)

    # --- Issue Link Operations ---

    async def link_issues(
        self, inward_key: str, outward_key: str, link_type: str = "Relates",
        comment: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> None:
        """Create a link between two issues (e.g. 'Blocks', 'Relates', 'Duplicate')."""
        url = f"{self.base_url}/issueLink"
        payload: Dict[str, Any] = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        if comment is not None:
            payload["comment"] = {"body": self.text_to_adf(comment)}
        await self._request("POST", url, json_data=payload)

    # --- Utility Methods ---

    @staticmethod
    def format_issue_summary(issue: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a clean summary from a raw Jira issue response."""
        fields = issue.get("fields", {}) or {}
        assignee = fields.get("assignee")
        reporter = fields.get("reporter")
        status = fields.get("status")
        priority = fields.get("priority")
        issue_type = fields.get("issuetype")
        project = fields.get("project")
        parent = fields.get("parent")
        return {
            "key": issue.get("key"),
            "id": issue.get("id"),
            "summary": fields.get("summary"),
            "description": JiraClient.adf_to_text(fields.get("description")),
            "type": issue_type.get("name") if isinstance(issue_type, dict) else None,
            "status": status.get("name") if isinstance(status, dict) else None,
            "priority": priority.get("name") if isinstance(priority, dict) else None,
            "assignee": assignee.get("displayName") if isinstance(assignee, dict) else None,
            "assignee_account_id": assignee.get("accountId") if isinstance(assignee, dict) else None,
            "reporter": reporter.get("displayName") if isinstance(reporter, dict) else None,
            "labels": fields.get("labels"),
            "project_key": project.get("key") if isinstance(project, dict) else None,
            "parent_key": parent.get("key") if isinstance(parent, dict) else None,
            "url": f"{issue.get('self', '').split('/rest/api/')[0]}/browse/{issue.get('key')}" if issue.get("self") else None,
            "created": fields.get("created"),
            "updated": fields.get("updated"),
        }

    @staticmethod
    def format_comment_summary(comment: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a clean summary from a raw Jira comment response."""
        author = comment.get("author")
        return {
            "id": comment.get("id"),
            "body": JiraClient.adf_to_text(comment.get("body")),
            "author": author.get("displayName") if isinstance(author, dict) else None,
            "created": comment.get("created"),
            "updated": comment.get("updated"),
        }
